"""Grafo fixo que interpreta uma WorkflowSpec dinâmica — padrão fan_out_sintese.

Topologia (espelha a referência dynamic-workflow-harness, ver memória do projeto):

    START → planner → revisar_plano → [fan-out: subagente × N] → avaliar → sintetizar → END
                          (attempt → verifier → commit, retry ≤ max_tentativas)
                                              (cobertura reprovada → interrupt() ao fundador)

Regras de fronteira (anti-lock-in):
- nós são funções puras que só falam com `cliente.chamar(papel, prompt)`;
- estado serializável; a spec é dado, não código;
- todo passo emite evento JSONL próprio (painel/auditoria), além do checkpointer.
"""
from __future__ import annotations

import json
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from .eventos import LogEventos
from .modelos import ClienteModelo, extrai_json
from .politica import PoliticaGates
from .spec import WorkflowSpec


def mesclar_resultados(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mescla commits de subagentes por id; commits mais novos substituem antigos."""
    por_id = {r["id"]: r for r in a}
    for resultado in b:
        por_id[resultado["id"]] = resultado
    return list(por_id.values())


class EstadoMotor(TypedDict, total=False):
    missao_texto: str
    spec: dict[str, Any]
    resultados: Annotated[list[dict[str, Any]], mesclar_resultados]
    avaliacao: dict[str, Any]
    resposta_final: str


PROMPT_PLANNER = """Você é o planner da meta-fábrica. Missão do usuário:
\"\"\"{missao}\"\"\"

Produza uma WorkflowSpec versão 0.1 em JSON (responda APENAS o JSON), conforme o schema:
{schema}

Regras: entre 2 e {max_sub} subagentes focados e INDEPENDENTES (depende_de sempre []);
cada subagente com rubrica objetiva e verificável; criterios_cobertura checáveis contra a missão;
padrao = "fan_out_sintese".
Subagentes podem ser executados por modelos de capacidade limitada: escreva cada objetivo sem
ambiguidade nem decisão de design implícita, e rubricas checáveis MECANICAMENTE (formato exigido,
números/evidências presentes, seções obrigatórias) — nunca critérios que dependem de bom gosto.
Para cada subagente, classifique o campo "tier" pela complexidade da tarefa (roteamento por custo):
"simples" (extração/formatação/lookup direto), "media" (pesquisa ou redação com algum raciocínio),
"complexa" (design, trade-offs, modelagem ou síntese que exige um modelo forte).{erro}"""

PROMPT_SUBAGENTE = """Você é o subagente '{id}' (papel: {papel}) de um workflow.
Missão global: {missao_objetivo}
Contexto: {missao_contexto}
Seu objetivo: {objetivo}
Entradas: {entradas}
Resultado esperado: {resultado_esperado}{feedback}

Entregue diretamente o resultado, específico e fundamentado."""

PROMPT_VERIFIER = """Você é o verificador adversarial do subagente '{id}'.
Objetivo dele: {objetivo}
Rubrica (TODOS os critérios precisam passar):
{rubrica}

Saída a avaliar:
\"\"\"{saida}\"\"\"

Seja cético: procure o que falta, não o que agrada. Responda APENAS um JSON:
{{"aprovado": true/false, "motivo": "específico e acionável"}}"""

PROMPT_EVALUATOR = """Você é o avaliador global de cobertura de um workflow.
Missão: {missao_objetivo}
Critérios de cobertura (TODOS precisam estar cobertos pelos resultados):
{criterios}

Resultados commitados:
{resultados}

Responda APENAS um JSON: {{"aprovado": true/false, "lacunas": ["o que falta", ...]}}"""

PROMPT_SYNTHESIZER = """Você é o sintetizador final de um workflow.
Missão: {missao_objetivo}
Instrução de síntese: {instrucao} (formato: {formato})

Resultados verificados dos subagentes:
{resultados}

Produza a resposta final da missão."""


def construir_grafo(cliente: ClienteModelo, log: LogEventos, checkpointer=None,
                    politica: PoliticaGates | None = None):
    """Compila o grafo. `cliente` e `log` são injetados — o grafo não conhece backends.
    `politica` decide quais gates pausam (manual) ou resolvem sozinhos (auto-mode);
    ausente = tudo manual (comportamento default)."""
    politica = politica or PoliticaGates()

    def planner(state: EstadoMotor) -> dict:
        if state.get("spec"):  # spec fornecida pelo usuário: valida e segue (missão dirigida por dado)
            spec = WorkflowSpec.model_validate(state["spec"])
            log.evento("spec.recebida", missao=spec.missao.id, subagentes=len(spec.subagentes))
            return {"spec": spec.model_dump()}
        erro = ""
        for tentativa in (1, 2, 3):
            log.evento("executor.chamado", executor="planner", tentativa=tentativa)
            resp = cliente.chamar("planner", PROMPT_PLANNER.format(
                missao=state["missao_texto"],
                schema=json.dumps(WorkflowSpec.model_json_schema(), ensure_ascii=False),
                max_sub=10, erro=erro))
            bruto = extrai_json(resp or "")
            if bruto is not None:
                try:
                    spec = WorkflowSpec.model_validate(bruto)
                    log.evento("spec.criada", missao=spec.missao.id, subagentes=len(spec.subagentes))
                    return {"spec": spec.model_dump()}
                except Exception as ex:  # validação pydantic reprovada → reinjeta o erro
                    erro = f"\n\nSua tentativa anterior falhou na validação: {ex}\nCorrija e reenvie só o JSON."
            log.evento("executor.erro", executor="planner", motivo="spec inválida ou sem JSON", tentativa=tentativa)
        raise RuntimeError("planner não produziu WorkflowSpec válida em 3 tentativas")

    def plano_de(spec: dict[str, Any]) -> list[dict[str, Any]]:
        plano = []
        for sub in spec["subagentes"]:
            modelo = (cliente.provedor_de(sub["papel"], sub.get("tier"), sub.get("ferramentas"))
                      if hasattr(cliente, "provedor_de") else None)
            plano.append({
                "id": sub["id"],
                "papel": sub["papel"],
                "tier": sub.get("tier"),
                "modelo": modelo,
            })
        return plano

    def revisar_plano(state: EstadoMotor) -> dict:
        spec = state["spec"]
        plano = plano_de(spec)
        auto = politica.decisao_auto("plano", default="prosseguir")
        if auto is not None:
            log.evento("gate.auto", portao="plano", decisao=auto)
            return {}

        log.evento("escalado", para="plano")
        decisao = interrupt({
            "portao": "plano",
            "plano": plano,
            "pergunta": "Revise o plano. prosseguir / editar / abortar",
            "opcoes": "prosseguir · editar · abortar",
        })

        if isinstance(decisao, dict):
            edicoes = dict(decisao)
            spec_editada = {**spec, "subagentes": [dict(s) for s in spec["subagentes"]]}
            for sub in spec_editada["subagentes"]:
                if sub["id"] in edicoes:
                    sub["tier"] = edicoes[sub["id"]]
            log.evento("decisao.plano", edicoes=edicoes)
            return {"spec": spec_editada}

        decisao_txt = str(decisao).strip().lower()
        log.evento("decisao.plano", decisao=str(decisao))
        if decisao_txt.startswith("abort"):
            return {"avaliacao": {"abortada": True, "motivo": "plano rejeitado"}}
        return {}

    def despachar(state: EstadoMotor):
        spec = state["spec"]
        log.evento("paralelo.iniciado", subagentes=[s["id"] for s in spec["subagentes"]])
        return [Send("subagente", {"sub": s, "spec": spec}) for s in spec["subagentes"]]

    def rota_pos_plano(state: EstadoMotor):
        if state.get("avaliacao", {}).get("abortada"):
            return END
        return despachar(state)

    def subagente(payload: dict) -> dict:
        sub, spec = payload["sub"], payload["spec"]
        missao = spec["missao"]
        max_t = spec["restricoes"]["max_tentativas"]
        # Guard de independência: o verifier deve evitar o provedor DO executor desta
        # tarefa (cross-model anti-auto-aprovação). Só quando o cliente sabe rotear.
        prov_exec = (cliente.provedor_de(sub["papel"], sub.get("tier"), sub.get("ferramentas"))
                     if hasattr(cliente, "provedor_de") else None)
        kw_verifier = {"evitar": prov_exec} if prov_exec else {}
        feedback, ultima = payload.get("feedback", ""), None
        for tentativa in range(1, max_t + 1):
            log.evento("executor.chamado", executor=sub["id"], papel=sub["papel"],
                       tier=sub.get("tier"), tentativa=tentativa)
            ultima = cliente.chamar(sub["papel"], PROMPT_SUBAGENTE.format(
                id=sub["id"], papel=sub["papel"],
                missao_objetivo=missao["objetivo"], missao_contexto=missao["contexto"],
                objetivo=sub["objetivo"], entradas=json.dumps(sub["entradas"], ensure_ascii=False),
                resultado_esperado=sub["resultado_esperado"],
                feedback=f"\nNa tentativa anterior o verificador reprovou: \"{feedback}\". Corrija." if feedback else "",
            ), ferramentas=sub.get("ferramentas"), tier=sub.get("tier"))
            if not ultima:
                feedback = "modelo não respondeu"
                log.evento("executor.erro", executor=sub["id"], motivo=feedback, tentativa=tentativa)
                continue
            log.evento("executor.respondeu", executor=sub["id"], tentativa=tentativa)
            veredito = extrai_json(cliente.chamar("verifier", PROMPT_VERIFIER.format(
                id=sub["id"], objetivo=sub["objetivo"],
                rubrica="\n".join(f"- {c}" for c in sub["rubrica"]), saida=ultima,
            ), **kw_verifier) or "") or {"aprovado": False, "motivo": "verifier sem JSON"}
            if veredito.get("aprovado"):
                log.evento("portao.aprovado", portao=f"verifier:{sub['id']}", ciclo=tentativa)
                return {"resultados": [{"id": sub["id"], "saida": ultima,
                                        "tentativas": tentativa, "aprovado": True}]}
            feedback = veredito.get("motivo", "sem motivo")
            log.evento("portao.reprovado", portao=f"verifier:{sub['id']}", ciclo=tentativa, motivo=feedback)
        return {"resultados": [{"id": sub["id"], "saida": ultima or "",
                                "tentativas": max_t, "aprovado": False, "motivo": feedback}]}

    def avaliar_cobertura(spec: dict[str, Any], resultados: list[dict[str, Any]]) -> dict[str, Any]:
        reprovados = [r["id"] for r in resultados if not r["aprovado"]]
        log.evento("executor.chamado", executor="global_evaluator")
        veredito = extrai_json(cliente.chamar("evaluator", PROMPT_EVALUATOR.format(
            missao_objetivo=spec["missao"]["objetivo"],
            criterios="\n".join(f"- {c}" for c in spec["missao"]["criterios_cobertura"]),
            resultados=json.dumps(resultados, ensure_ascii=False),
        )) or "") or {"aprovado": False, "lacunas": ["evaluator sem JSON"]}
        if reprovados:
            veredito = {"aprovado": False,
                        "lacunas": list(veredito.get("lacunas", [])) + [f"subagente reprovado: {i}" for i in reprovados]}
        return veredito

    def decidir_cobertura(veredito: dict[str, Any], permitir_preencher: bool) -> Any:
        auto = politica.decisao_auto("cobertura", default="prosseguir")
        if auto == "preencher" and not permitir_preencher:
            auto = "prosseguir"
        if auto is not None:  # auto-mode (ou override): resolve sozinho, sem pausar
            log.evento("gate.auto", portao="cobertura", decisao=auto)
            return auto

        log.evento("escalado", para="fundador")
        opcoes = "prosseguir · preencher · abortar" if permitir_preencher else "prosseguir · abortar"
        pergunta = ("Cobertura insuficiente. Prosseguir com síntese parcial, preencher lacunas ou abortar?"
                    if permitir_preencher else
                    "Cobertura insuficiente. Prosseguir com síntese parcial ou abortar?")
        decisao = interrupt({  # pausa durável: o checkpointer segura até Command(resume=...)
            "portao": "cobertura",
            "pergunta": pergunta,
            "lacunas": veredito.get("lacunas", []),
            "opcoes": opcoes,
        })
        log.evento("decisao.fundador", portao="cobertura", decisao=str(decisao))
        return decisao

    def preencher_lacunas(spec: dict[str, Any], resultados: list[dict[str, Any]],
                          veredito: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        reprovados = {r["id"] for r in resultados if not r["aprovado"]}
        lacunas = [str(l) for l in veredito.get("lacunas", [])]
        ids = [sid for sid in reprovados if any(sid in lacuna for lacuna in lacunas)]
        if not ids:
            return resultados, []

        por_id = {s["id"]: s for s in spec["subagentes"]}
        novos: list[dict[str, Any]] = []
        for sid in ids:
            feedback = "; ".join(l for l in lacunas if sid in l)
            retorno = subagente({"sub": por_id[sid], "spec": spec, "feedback": feedback})
            novos.extend(retorno["resultados"])
            log.evento("lacuna.preenchida", subagente=sid)
        return mesclar_resultados(resultados, novos), novos

    def finalizar_cobertura(veredito: dict[str, Any], decisao: Any) -> dict[str, Any]:
        if str(decisao).strip().lower().startswith("abort"):
            log.evento("tarefa.abortada", motivo="decisão do fundador")
            return {**veredito, "abortada": True}
        return {**veredito, "prosseguir_parcial": True}

    def avaliar(state: EstadoMotor) -> dict:
        spec, resultados = state["spec"], state["resultados"]
        log.evento("paralelo.concluido", commitados=len(resultados))
        veredito = avaliar_cobertura(spec, resultados)
        if veredito.get("aprovado"):
            log.evento("portao.aprovado", portao="cobertura")
            return {"avaliacao": veredito}
        log.evento("portao.reprovado", portao="cobertura", lacunas=veredito.get("lacunas", []))
        decisao = decidir_cobertura(veredito, permitir_preencher=True)

        if str(decisao).strip().lower().startswith("preench"):
            resultados, novos = preencher_lacunas(spec, resultados, veredito)
            if novos:
                veredito = avaliar_cobertura(spec, resultados)
                if veredito.get("aprovado"):
                    log.evento("portao.aprovado", portao="cobertura")
                    return {"resultados": novos, "avaliacao": veredito}
                log.evento("portao.reprovado", portao="cobertura", lacunas=veredito.get("lacunas", []))
            decisao = decidir_cobertura(veredito, permitir_preencher=False)
            return {"resultados": novos, "avaliacao": finalizar_cobertura(veredito, decisao)}

        return {"avaliacao": finalizar_cobertura(veredito, decisao)}

    def rota_pos_avaliacao(state: EstadoMotor):
        return END if state["avaliacao"].get("abortada") else "sintetizar"

    def sintetizar(state: EstadoMotor) -> dict:
        spec = state["spec"]
        log.evento("executor.chamado", executor="synthesizer")
        resposta = cliente.chamar("synthesizer", PROMPT_SYNTHESIZER.format(
            missao_objetivo=spec["missao"]["objetivo"],
            instrucao=spec["sintese"]["instrucao"], formato=spec["sintese"]["formato"],
            resultados=json.dumps([r for r in state["resultados"] if r["aprovado"]], ensure_ascii=False),
        )) or "(synthesizer não respondeu)"
        log.evento("tarefa.concluida", missao=spec["missao"]["id"])
        return {"resposta_final": resposta}

    g = StateGraph(EstadoMotor)
    g.add_node("planner", planner)
    g.add_node("revisar_plano", revisar_plano)
    g.add_node("subagente", subagente)  # type: ignore[arg-type]
    g.add_node("avaliar", avaliar)
    g.add_node("sintetizar", sintetizar)
    g.add_edge(START, "planner")
    g.add_edge("planner", "revisar_plano")
    g.add_conditional_edges("revisar_plano", rota_pos_plano, ["subagente", END])
    g.add_edge("subagente", "avaliar")
    g.add_conditional_edges("avaliar", rota_pos_avaliacao, ["sintetizar", END])
    g.add_edge("sintetizar", END)
    return g.compile(checkpointer=checkpointer)
