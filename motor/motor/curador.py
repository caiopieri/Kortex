"""Observador read-only para perfis de aptidao a partir de logs JSONL."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SEM_TIER = "sem-tier"
DESCONHECIDO = "desconhecido"


def carregar_runs(caminhos: list[str | Path], incluir_rascunho: bool = False) -> tuple[list[dict[str, Any]], int]:
    runs: list[dict[str, Any]] = []
    malformadas = 0
    for arquivo in _expandir(caminhos):
        eventos: list[dict[str, Any]] = []
        indice = 1
        ultimo_t: float | None = None
        with arquivo.open(encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    ev = json.loads(linha)
                except json.JSONDecodeError:
                    malformadas += 1
                    continue
                if not isinstance(ev, dict):
                    malformadas += 1
                    continue
                t = _num(ev.get("t"))
                if eventos and t is not None and ultimo_t is not None and t < ultimo_t:
                    _adicionar_run(runs, arquivo, indice, eventos, incluir_rascunho)
                    eventos, indice = [], indice + 1
                eventos.append(ev)
                ultimo_t = t if t is not None else ultimo_t
        if eventos:
            _adicionar_run(runs, arquivo, indice, eventos, incluir_rascunho)
    return runs, malformadas


def analisar(
    caminhos: list[str | Path],
    precos: dict[str, Any] | None = None,
    incluir_rascunho: bool = False,
) -> dict[str, Any]:
    runs, malformadas = carregar_runs(caminhos, incluir_rascunho=incluir_rascunho)
    agregador = _Agregador()
    por_papel_tier, por_modelo, por_slot_modelo = agregador.consumir_runs(runs)
    return {
        "versao": 1,
        "fontes": sorted({run["fonte"] for run in runs}),
        "linhas_malformadas": malformadas,
        "por_papel_tier": por_papel_tier,
        "por_modelo": por_modelo,
        "por_slot_modelo": por_slot_modelo,
        "por_template_versao": agregador.finalizar_template_versao(),
        "custo": _LedgerCusto(precos).consumir_runs(runs),
        "runs": [_analisar_run(run) for run in runs],
    }


def formatar_markdown(perfil: dict[str, Any]) -> str:
    linhas = [
        "# Perfil do Curador",
        "",
        f"- fontes: {len(perfil['fontes'])}",
        f"- runs: {len(perfil['runs'])}",
        f"- linhas malformadas ignoradas: {perfil['linhas_malformadas']}",
        "",
        "## Aptidao por papel/tier",
    ]
    perfis = perfil["por_papel_tier"]
    if not perfis:
        linhas.append("- sem eventos agregaveis")
    for papel in sorted(perfis):
        for tier in sorted(perfis[papel]):
            m, lat = perfis[papel][tier], perfis[papel][tier]["latencia"]
            linhas.append(
                f"- {papel}/{tier}: chamadas {m['chamadas']}, respostas {m['respostas']}, "
                f"erros {m['erros']} ({_pct(m['taxa_erro'])}), "
                f"incompletas {m['incompletas']} ({_pct(m['taxa_incompletas'])}), "
                f"aprovacao verifier 1a tentativa {_pct(m['taxa_aprovacao_primeira'])}, "
                f"reprovacoes {m['reprovacoes']}, escaladas {m['escaladas']} "
                f"(convergencia {_pct(m['taxa_convergencia_pos_escalada'])}), "
                f"latencia mediana {_seg(lat['mediana'])}, p90 {_seg(lat['p90'])}"
            )
            if m["amostras_motivos"]:
                linhas.append(f"  motivos: {'; '.join(m['amostras_motivos'])}")

    linhas += ["", "## Aptidao por modelo"]
    modelos = perfil["por_modelo"]
    if not modelos:
        linhas.append("- sem eventos agregaveis")
    for modelo in _ordenar_modelos(modelos):
        m, lat = modelos[modelo], modelos[modelo]["latencia"]
        linhas.append(
            f"- {modelo}: chamadas {m['chamadas']}, respostas {m['respostas']}, "
            f"erros {m['erros']} ({_pct(m['taxa_erro'])}), "
            f"incompletas {m['incompletas']} ({_pct(m['taxa_incompletas'])}), "
            f"falhas internas {m['falhas_internas']}, "
            f"aprovacao verifier 1a tentativa {_pct(m['taxa_aprovacao_primeira'])}, "
            f"reprovacoes {m['reprovacoes']}, escaladas {m['escaladas']} "
            f"(convergencia {_pct(m['taxa_convergencia_pos_escalada'])}), "
            f"latencia mediana {_seg(lat['mediana'])}, p90 {_seg(lat['p90'])}"
        )
        if m["amostras_motivos"]:
            linhas.append(f"  motivos: {'; '.join(m['amostras_motivos'])}")

    linhas += ["", "## Aptidao por template/versao"]
    templates = perfil["por_template_versao"]
    if not templates:
        linhas.append("- sem eventos agregaveis")
    for template_versao in sorted(templates):
        m, lat = templates[template_versao], templates[template_versao]["latencia"]
        linhas.append(
            f"- {template_versao}: chamadas {m['chamadas']}, respostas {m['respostas']}, "
            f"erros {m['erros']} ({_pct(m['taxa_erro'])}), "
            f"incompletas {m['incompletas']} ({_pct(m['taxa_incompletas'])}), "
            f"falhas internas {m['falhas_internas']}, "
            f"aprovacao verifier 1a tentativa {_pct(m['taxa_aprovacao_primeira'])}, "
            f"reprovacoes {m['reprovacoes']}, escaladas {m['escaladas']} "
            f"(convergencia {_pct(m['taxa_convergencia_pos_escalada'])}), "
            f"latencia mediana {_seg(lat['mediana'])}, p90 {_seg(lat['p90'])}"
        )
        if m["amostras_motivos"]:
            linhas.append(f"  motivos: {'; '.join(m['amostras_motivos'])}")

    linhas += ["", "## Runs"]
    if not perfil["runs"]:
        linhas.append("- nenhum run encontrado")
    for run in perfil["runs"]:
        p, c, r = run["planner"], run["cobertura"], run["resiliencia"]
        linhas.append(
            f"- {run['id']}: planner {p['tentativas_ate_spec_criada']} tentativa(s), "
            f"latencia {_seg(p['latencia_ate_spec_criada'])}; "
            f"cobertura reconciliada={c['reprovado_para_aprovado_via_reconciliacao']} "
            f"rodadas={c['rodadas_reconciliacao']} closures={c['closure_por_rodada']}; "
            f"resiliencia eventos={r['total_eventos']} 429={len(r['motivos_429'])}"
        )
    return "\n".join(linhas) + "\n"


def propor(
    perfil: dict[str, Any],
    min_amostras: int = 3,
    custo: dict[str, Any] | None = None,
    piso_aprovacao: float = 0.6,
    limiar_falha: float = 0.5,
) -> dict[str, Any]:
    """Ranqueia modelos por slot sem aplicar mudancas.

    Score de qualidade = aprovacao_1a - taxa_erro - penalidade de escalada nao convergida.
    A penalidade de escalada so entra quando houve escalada no slot/modelo. O score decide
    qualidade; empates sao resolvidos por menor latencia mediana e, se informado, menor custo.
    """
    custo_ordem = _normalizar_custo(custo)
    custo_real = _custo_real_por_modelo(perfil)
    slots: dict[str, Any] = {}
    for slot in sorted(perfil.get("por_slot_modelo", {})):
        modelos = perfil["por_slot_modelo"][slot]
        candidatos = [
            (modelo, metricas)
            for modelo, metricas in modelos.items()
            if metricas["verifier_julgados"] >= min_amostras
        ]
        evitar = _modelos_a_evitar(modelos, min_amostras, limiar_falha)
        if not candidatos:
            maior = max((m["verifier_julgados"] for m in modelos.values()), default=0)
            slots[slot] = {"status": "evidencia_insuficiente", "amostras": maior}
            if evitar:
                slots[slot]["evitar"] = evitar
            continue

        ranking = []
        for modelo, metricas in candidatos:
            ranking.append(_item_ranking(modelo, metricas, custo_ordem, custo_real))
        ranking.sort(key=_chave_ranking)
        for item in ranking:
            item.pop("_custo", None)
        recomendado = ranking[0]
        status = "proposto"
        aviso = None
        if recomendado["aprov_1a"] < piso_aprovacao:
            status = "melhor_disponivel_abaixo_do_piso"
            aviso = (
                f"aprovacao {_pct(recomendado['aprov_1a'])} < piso {_pct(piso_aprovacao)}; "
                "nao confie sem mais evidencia"
            )
        slots[slot] = {
            "status": status,
            "recomendado": recomendado["modelo"],
            "ranking": ranking,
            "evitar": evitar,
        }
        if aviso:
            slots[slot]["aviso"] = aviso
        if len(candidatos) == 1:
            slots[slot]["unico_candidato"] = True

    return {
        "versao": 1,
        "min_amostras": min_amostras,
        "piso_aprovacao": piso_aprovacao,
        "limiar_falha": limiar_falha,
        "slots": slots,
    }


def formatar_proposta_markdown(proposta: dict[str, Any]) -> str:
    linhas = [
        "# Proposta do Curador",
        "",
        f"- min_amostras: {proposta['min_amostras']}",
        "- modo: read-only",
        "",
    ]
    slots = proposta["slots"]
    if not slots:
        linhas.append("- sem slots agregaveis")
        return "\n".join(linhas) + "\n"

    for slot in sorted(slots):
        info = slots[slot]
        linhas += [f"## {slot}"]
        linhas.append(f"- status: {info['status']}")
        if info["status"] == "evidencia_insuficiente":
            linhas.append(f"- evidencia insuficiente: maior amostra {info['amostras']}")
            if info.get("evitar"):
                linhas.append(f"- evitar: {', '.join(info['evitar'])}")
            linhas.append("")
            continue

        linhas.append(f"- recomendado: {info['recomendado']}")
        if info.get("aviso"):
            linhas.append(f"- aviso: {info['aviso']}")
        if info.get("unico_candidato"):
            linhas.append("- unico_candidato: true")
        linhas.append("")
        linhas.append(
            "| modelo | score | aprov_1a | taxa_erro | incompletas | taxa_incompletas | "
            "latencia_mediana | amostras |"
        )
        linhas.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for item in info["ranking"]:
            linhas.append(
                f"| {item['modelo']} | {item['score']:.4f} | {_pct(item['aprov_1a'])} | "
                f"{_pct(item['taxa_erro'])} | {item['incompletas']} | {_pct(item['taxa_incompletas'])} | "
                f"{_seg(item['latencia_mediana'])} | {item['amostras']} |"
            )
        if info["evitar"]:
            linhas.append(f"- evitar: {', '.join(info['evitar'])}")
        linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"


def formatar_custo_markdown(custo: dict[str, Any]) -> str:
    linhas = [
        "# Livro-razão de Custo",
        "",
        "## Total",
        _linha_custo_total(custo["total"]),
        "",
        "## Por modelo",
    ]
    modelos = custo["por_modelo"]
    if not modelos:
        linhas.append("- sem eventos agregaveis")
    else:
        linhas.append(
            "| modelo | chamadas_com_uso | tokens_prompt | tokens_completion | tokens_total | "
            "tempo_total_s | custo_usd |"
        )
        linhas.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for modelo in sorted(modelos):
            m = modelos[modelo]
            linhas.append(
                f"| {modelo} | {m['chamadas_com_uso']} | {_int_md(m['tokens_prompt'])} | "
                f"{_int_md(m['tokens_completion'])} | {_int_md(m['tokens_total'])} | "
                f"{_seg(m['tempo_total_s'])} | {_usd(m['custo_usd'])} |"
            )

    linhas += ["", "## Por slot/modelo"]
    slots = custo.get("por_slot_modelo", {})
    if not slots:
        linhas.append("- sem eventos agregaveis")
    else:
        linhas.append(
            "| slot | modelo | chamadas_com_uso | tokens_prompt | tokens_completion | tokens_total | "
            "tempo_total_s | custo_usd |"
        )
        linhas.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for slot in sorted(slots):
            for modelo in sorted(slots[slot]):
                m = slots[slot][modelo]
                linhas.append(
                    f"| {slot} | {modelo} | {m['chamadas_com_uso']} | {_int_md(m['tokens_prompt'])} | "
                    f"{_int_md(m['tokens_completion'])} | {_int_md(m['tokens_total'])} | "
                    f"{_seg(m['tempo_total_s'])} | {_usd(m['custo_usd'])} |"
                )

    linhas += ["", "## Por run"]
    runs = custo["por_run"]
    if not runs:
        linhas.append("- nenhum run encontrado")
    else:
        linhas.append(
            "| run | fonte | tokens_prompt | tokens_completion | tokens_total | tempo_total_s | custo_usd |"
        )
        linhas.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
        for run in runs:
            linhas.append(
                f"| {run['id']} | {run['fonte']} | {_int_md(run['tokens_prompt'])} | "
                f"{_int_md(run['tokens_completion'])} | {_int_md(run['tokens_total'])} | "
                f"{_seg(run['tempo_total_s'])} | {_usd(run['custo_usd'])} |"
            )
    return "\n".join(linhas).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m motor.curador",
        description="Gera perfil read-only de aptidao a partir de logs JSONL.",
    )
    parser.add_argument("caminhos", nargs="+")
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--propor", action="store_true", help="imprime proposta read-only por slot/modelo")
    parser.add_argument("--min-amostras", type=int, default=3)
    parser.add_argument(
        "--custo",
        nargs="?",
        const="",
        help="sem --propor: imprime ledger de custo e aceita precos.json opcional; com --propor: JSON de ordem de custo",
    )
    parser.add_argument("--piso", type=float, default=0.6, help="piso de aprovacao 1a tentativa para proposta limpa")
    parser.add_argument("--limiar-falha", type=float, default=0.5, help="limiar de erro+incompleta para evitar modelo")
    parser.add_argument("--incluir-rascunho", action="store_true", help="inclui runs marcados como rascunho")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    perfil = analisar(
        args.caminhos,
        precos=_parse_precos(args.custo) if args.custo is not None and not args.propor else None,
        incluir_rascunho=args.incluir_rascunho,
    )
    if args.json_path:
        args.json_path.write_text(
            json.dumps(perfil, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.propor:
        print(
            formatar_proposta_markdown(
                propor(
                    perfil,
                    min_amostras=args.min_amostras,
                    custo=_parse_custo(args.custo),
                    piso_aprovacao=args.piso,
                    limiar_falha=args.limiar_falha,
                )
            ),
            end="",
        )
    elif args.custo is not None:
        print(formatar_custo_markdown(perfil["custo"]), end="")
    else:
        print(formatar_markdown(perfil), end="")
    return 0


class _Agregador:
    def __init__(self) -> None:
        self.por_papel_tier: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(_metricas))
        self.por_modelo: dict[str, dict[str, Any]] = defaultdict(_metricas)
        self.por_slot_modelo: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(_metricas)
        self.por_template_versao: dict[str, dict[str, Any]] = defaultdict(_metricas)

    def consumir_runs(
        self,
        runs: list[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
        for run in runs:
            self._consumir_run(run["eventos"])
        return self._finalizar_papel_tier(), self._finalizar_modelos(), self._finalizar_slot_modelo()

    def _consumir_run(self, eventos: list[dict[str, Any]]) -> None:
        chamadas: dict[tuple[str, int | None], dict[str, Any]] = {}
        chamadas_concluidas: set[tuple[str, int | None]] = set()
        ultimo_executor: dict[str, dict[str, Any]] = {}
        tier_por_papel: dict[str, str] = {}
        modelo_por_papel: dict[str, str] = {}
        escaladas: list[dict[str, Any]] = []

        def chamada(ev: dict[str, Any]) -> dict[str, Any] | None:
            executor = _str(ev.get("executor")) or "desconhecido"
            return chamadas.get((executor, _int(ev.get("tentativa")))) or ultimo_executor.get(executor)

        for ev in eventos:
            tipo, tempo = ev.get("evento"), _num(ev.get("t"))
            if tipo in {"modelo.roteado_tier", "modelo.pin"}:
                if papel := _str(ev.get("papel")):
                    tier_por_papel[papel] = _tier(ev.get("tier"))
            elif tipo == "executor.chamado":
                executor = _str(ev.get("executor")) or "desconhecido"
                tentativa = _int(ev.get("tentativa"))
                papel = _str(ev.get("papel")) or executor
                tier = _tier(ev.get("tier"))
                modelo = _str(ev.get("modelo")) or DESCONHECIDO
                info: dict[str, Any] = {
                    "executor": executor,
                    "tentativa": tentativa,
                    "papel": papel,
                    "tier": tier,
                    "modelo": modelo,
                    "template_versao": _template_versao(ev),
                    "t": tempo,
                }
                chamadas[(executor, tentativa)] = info
                ultimo_executor[executor] = info
                tier_por_papel[papel] = tier
                modelo_por_papel[papel] = modelo
                self._inc(info, "chamadas")
            elif tipo in {"executor.respondeu", "executor.erro"}:
                chave_chamada = _chave_chamada(ev)
                info_pareado = chamadas.get(chave_chamada)
                info_fallback = None if info_pareado is not None else chamada(ev)
                info_metricas = info_pareado or info_fallback or self._desconhecido()
                if chave_chamada in chamadas:
                    chamadas_concluidas.add(chave_chamada)
                elif info_fallback is not None:
                    chamadas_concluidas.add((info_fallback["executor"], info_fallback["tentativa"]))
                self._inc(info_metricas, "respostas" if tipo == "executor.respondeu" else "erros")
                if info_metricas["t"] is not None and tempo is not None:
                    self._append(info_metricas, "_latencias", round(max(0.0, tempo - info_metricas["t"]), 3))
            elif tipo == "modelo.falha":
                papel = _str(ev.get("papel")) or "desconhecido"
                info = {
                    "papel": papel,
                    "tier": tier_por_papel.get(papel, SEM_TIER),
                    "modelo": _str(ev.get("modelo")) or modelo_por_papel.get(papel, DESCONHECIDO),
                    "template_versao": _template_versao(ev),
                }
                self._inc(info, "falhas_internas")
            elif tipo == "executor.escalado":
                executor = _str(ev.get("executor")) or "desconhecido"
                info = ultimo_executor.get(executor, self._desconhecido())
                origem = {
                    "papel": info["papel"],
                    "tier": _tier(ev.get("de") or info["tier"]),
                    "modelo": info["modelo"],
                }
                self._inc(origem, "escaladas")
                escaladas.append({"executor": executor, "t": tempo, "origem": origem, "ok": False})
            elif tipo in {"portao.aprovado", "portao.reprovado"} and _verifier(ev):
                self._julgar(ev, tempo, ultimo_executor, escaladas)
        for chave, info in chamadas.items():
            if chave not in chamadas_concluidas:
                self._inc(info, "incompletas")

    def _julgar(
        self,
        ev: dict[str, Any],
        tempo: float | None,
        ultimo_executor: dict[str, dict[str, Any]],
        escaladas: list[dict[str, Any]],
    ) -> None:
        executor = str(ev.get("portao", "")).split(":", 1)[1]
        info = ultimo_executor.get(executor, self._desconhecido())
        self._inc(info, "verifier_julgados")
        if ev.get("evento") == "portao.aprovado":
            if _int(ev.get("ciclo")) == 1:
                self._inc(info, "verifier_aprovados_primeira")
            for esc in escaladas:
                if esc["executor"] == executor and not esc["ok"] and _depois(tempo, esc["t"]):
                    esc["ok"] = True
                    self._inc(esc["origem"], "escaladas_convergidas")
            return

        self._inc(info, "reprovacoes")
        motivo = _motivo(ev)
        if motivo:
            self._append_motivo(info, motivo)

    def _finalizar_papel_tier(self) -> dict[str, dict[str, dict[str, Any]]]:
        saida: dict[str, dict[str, dict[str, Any]]] = {}
        for papel in sorted(self.por_papel_tier):
            saida[papel] = {}
            for tier in sorted(self.por_papel_tier[papel]):
                saida[papel][tier] = _finalizar_metricas(self.por_papel_tier[papel][tier])
        return saida

    def _finalizar_modelos(self) -> dict[str, dict[str, Any]]:
        return {modelo: _finalizar_metricas(self.por_modelo[modelo]) for modelo in sorted(self.por_modelo)}

    def _finalizar_slot_modelo(self) -> dict[str, dict[str, dict[str, Any]]]:
        saida: dict[str, dict[str, dict[str, Any]]] = {}
        for papel, tier, modelo in sorted(self.por_slot_modelo):
            slot = f"{papel}/{tier}"
            saida.setdefault(slot, {})
            saida[slot][modelo] = _finalizar_metricas(self.por_slot_modelo[(papel, tier, modelo)])
        return saida

    def finalizar_template_versao(self) -> dict[str, dict[str, Any]]:
        return {
            template_versao: _finalizar_metricas(self.por_template_versao[template_versao])
            for template_versao in sorted(self.por_template_versao)
        }

    def _metricas(
        self,
        info: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        modelo = info.get("modelo") or DESCONHECIDO
        return (
            self.por_papel_tier[info["papel"]][info["tier"]],
            self.por_modelo[modelo],
            self.por_slot_modelo[(info["papel"], info["tier"], modelo)],
            self.por_template_versao[info.get("template_versao") or DESCONHECIDO],
        )

    def _inc(self, info: dict[str, Any], campo: str) -> None:
        for metricas in self._metricas(info):
            metricas[campo] += 1

    def _append(self, info: dict[str, Any], campo: str, valor: Any) -> None:
        for metricas in self._metricas(info):
            metricas[campo].append(valor)

    def _append_motivo(self, info: dict[str, Any], motivo: str) -> None:
        for metricas in self._metricas(info):
            if motivo not in metricas["amostras_motivos"] and len(metricas["amostras_motivos"]) < 3:
                metricas["amostras_motivos"].append(motivo)

    def _desconhecido(self) -> dict[str, Any]:
        return {"papel": DESCONHECIDO, "tier": SEM_TIER, "modelo": DESCONHECIDO, "t": None}


class _LedgerCusto:
    def __init__(self, precos: dict[str, Any] | None = None) -> None:
        self.precos = _normalizar_precos(precos)
        self.por_modelo: dict[str, dict[str, Any]] = defaultdict(_metricas_custo)
        self.por_slot_modelo: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(_metricas_custo)

    def consumir_runs(self, runs: list[dict[str, Any]]) -> dict[str, Any]:
        por_run = []
        total = _metricas_custo()
        for run in runs:
            metricas_run = self._consumir_run(run)
            _somar_custo(total, metricas_run)
            por_run.append({
                "id": run["id"],
                "fonte": run["fonte"],
                **_finalizar_custo(metricas_run),
            })
        return {
            "por_run": por_run,
            "por_modelo": self._finalizar_modelos(),
            "por_slot_modelo": self._finalizar_slots(),
            "total": _finalizar_custo(total),
        }

    def _consumir_run(self, run: dict[str, Any]) -> dict[str, Any]:
        metricas_run = _metricas_custo()
        chamadas: dict[tuple[str, int | None], dict[str, Any]] = {}
        ultimo_executor: dict[str, dict[str, Any]] = {}
        ultimo_por_papel: dict[str, dict[str, Any]] = {}

        def chamada(ev: dict[str, Any]) -> dict[str, Any] | None:
            executor = _str(ev.get("executor")) or DESCONHECIDO
            return chamadas.get((executor, _int(ev.get("tentativa")))) or ultimo_executor.get(executor)

        for ev in run["eventos"]:
            tipo, tempo = ev.get("evento"), _num(ev.get("t"))
            if tipo == "executor.chamado":
                executor = _str(ev.get("executor")) or DESCONHECIDO
                tentativa = _int(ev.get("tentativa"))
                papel = _str(ev.get("papel")) or executor
                info: dict[str, Any] = {
                    "executor": executor,
                    "tentativa": tentativa,
                    "papel": papel,
                    "tier": _tier(ev.get("tier")),
                    "modelo": _modelo_custo(ev),
                    "t": tempo,
                }
                chamadas[(executor, tentativa)] = info
                ultimo_executor[executor] = info
                ultimo_por_papel[papel] = info
            elif tipo in {"executor.respondeu", "executor.erro"}:
                info_exec = chamada(ev)
                if info_exec and info_exec["t"] is not None and tempo is not None:
                    self._somar_tempo(metricas_run, info_exec, round(max(0.0, tempo - info_exec["t"]), 3))
            elif tipo == "modelo.uso":
                papel = _str(ev.get("papel")) or DESCONHECIDO
                modelo = _modelo_uso(ev)
                info_chamada = ultimo_por_papel.get(papel)
                info = {
                    "papel": papel,
                    "tier": info_chamada["tier"] if info_chamada else SEM_TIER,
                    "modelo": modelo,
                }
                self._somar_uso(metricas_run, info, ev)
        return metricas_run

    def _somar_tempo(self, metricas_run: dict[str, Any], info: dict[str, Any], segundos: float) -> None:
        for metricas in [metricas_run, *self._metricas(info)]:
            metricas["tempo_total_s"] += segundos

    def _somar_uso(self, metricas_run: dict[str, Any], info: dict[str, Any], ev: dict[str, Any]) -> None:
        prompt = _token(ev.get("prompt_tokens"))
        completion = _token(ev.get("completion_tokens"))
        total = _token(ev.get("total_tokens"))
        if total == 0 and (prompt or completion):
            total = prompt + completion
        custo_usd = self._calcular_usd(info["modelo"], prompt, completion)
        for metricas in [metricas_run, *self._metricas(info)]:
            metricas["chamadas_com_uso"] += 1
            metricas["tokens_prompt"] += prompt
            metricas["tokens_completion"] += completion
            metricas["tokens_total"] += total
            if custo_usd is not None:
                metricas["_custos_usd"].append(custo_usd)

    def _calcular_usd(self, modelo: str, prompt: int, completion: int) -> float | None:
        preco = self.precos.get(modelo)
        if preco is None:
            return None
        return prompt / 1000 * preco["in_por_1k"] + completion / 1000 * preco["out_por_1k"]

    def _metricas(self, info: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        modelo = info.get("modelo") or DESCONHECIDO
        return (
            self.por_modelo[modelo],
            self.por_slot_modelo[(info["papel"], info["tier"], modelo)],
        )

    def _finalizar_modelos(self) -> dict[str, dict[str, Any]]:
        return {modelo: _finalizar_custo(self.por_modelo[modelo]) for modelo in sorted(self.por_modelo)}

    def _finalizar_slots(self) -> dict[str, dict[str, dict[str, Any]]]:
        saida: dict[str, dict[str, dict[str, Any]]] = {}
        for papel, tier, modelo in sorted(self.por_slot_modelo):
            slot = f"{papel}/{tier}"
            saida.setdefault(slot, {})
            saida[slot][modelo] = _finalizar_custo(self.por_slot_modelo[(papel, tier, modelo)])
        return saida


def _analisar_run(run: dict[str, Any]) -> dict[str, Any]:
    first_planner_t = spec_t = None
    planner_attempts = 0
    spec_criada = cobertura_reprovada = cobertura_aprovada = recon = False
    closures: list[int] = []
    resiliencia = {
        "provedor_auto_esgotado": {},
        "modelo_reroteado_esgotado": {},
        "modelo_fallback": {},
        "falhas_modelo_429": {},
        "motivos_429": [],
        "total_eventos": 0,
    }

    for ev in run["eventos"]:
        tipo, tempo = ev.get("evento"), _num(ev.get("t"))
        if tipo == "executor.chamado" and ev.get("executor") == "planner" and not spec_criada:
            planner_attempts += 1
            first_planner_t = tempo if first_planner_t is None else first_planner_t
        elif tipo == "spec.criada" and not spec_criada:
            spec_criada, spec_t = True, tempo

        if tipo == "portao.reprovado" and ev.get("portao") == "cobertura":
            cobertura_reprovada = True
        elif tipo == "reconciliacao.iniciada" and cobertura_reprovada and not cobertura_aprovada:
            recon = True
            nos = ev.get("nos")
            closures.append(len(nos) if isinstance(nos, list) else 0)
        elif tipo == "portao.aprovado" and ev.get("portao") == "cobertura":
            cobertura_aprovada = True

        _resiliencia(resiliencia, ev)

    return {
        "id": run["id"],
        "fonte": run["fonte"],
        "eventos": len(run["eventos"]),
        "planner": {
            "tentativas_ate_spec_criada": planner_attempts,
            "latencia_ate_spec_criada": _delta(first_planner_t, spec_t),
        },
        "cobertura": {
            "reprovada": cobertura_reprovada,
            "aprovada": cobertura_aprovada,
            "reprovado_para_aprovado_via_reconciliacao": bool(cobertura_reprovada and cobertura_aprovada and recon),
            "rodadas_reconciliacao": len(closures),
            "closure_por_rodada": closures,
        },
        "resiliencia": resiliencia,
    }


def _resiliencia(alvo: dict[str, Any], ev: dict[str, Any]) -> None:
    tipo = ev.get("evento")
    if tipo == "provedor.auto_esgotado":
        alvo["total_eventos"] += 1
        _inc2(alvo["provedor_auto_esgotado"], _str(ev.get("provedor")) or "desconhecido", _papel(ev))
    elif tipo == "modelo.reroteado_esgotado":
        alvo["total_eventos"] += 1
        rota = f"{_str(ev.get('de')) or 'desconhecido'}->{_str(ev.get('para')) or 'desconhecido'}"
        _inc2(alvo["modelo_reroteado_esgotado"], rota, _papel(ev))
    elif tipo == "modelo.fallback":
        alvo["total_eventos"] += 1
        _inc2(alvo["modelo_fallback"], _str(ev.get("para")) or "desconhecido", _papel(ev))
    elif tipo == "modelo.falha" and "429" in (_str(ev.get("motivo")) or ""):
        _inc2(alvo["falhas_modelo_429"], _papel(ev), "ocorrencias")
    else:
        return
    if "429" in (_str(ev.get("motivo")) or ""):
        alvo["motivos_429"].append(
            {"evento": tipo, "papel": ev.get("papel"), "provedor": ev.get("provedor"), "motivo": ev.get("motivo")}
        )


def _parse_precos(valor: str | None) -> dict[str, Any] | None:
    if not valor:
        return None
    path = Path(valor)
    try:
        texto = path.read_text(encoding="utf-8") if path.is_file() else valor
        parsed = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--custo precisa ser um precos.json valido: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit("--custo precisa ser um objeto JSON de precos")
    return parsed


def _parse_custo(valor: str | None) -> dict[str, Any] | None:
    if valor is None:
        return None
    if valor == "":
        raise SystemExit("--propor --custo exige JSON com ordem de custo")
    try:
        parsed = json.loads(valor)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--custo precisa ser JSON valido: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit("--custo precisa ser um objeto JSON")
    return parsed


def _normalizar_custo(custo: dict[str, Any] | None) -> dict[str, int]:
    if not custo:
        return {}
    saida = {}
    for modelo, ordem in custo.items():
        try:
            saida[str(modelo)] = int(ordem)
        except (TypeError, ValueError):
            continue
    return saida


def _custo_real_por_modelo(perfil: dict[str, Any]) -> dict[str, float]:
    saida: dict[str, float] = {}
    por_modelo = perfil.get("custo", {}).get("por_modelo", {})
    if not isinstance(por_modelo, dict):
        return saida
    for modelo, metricas in por_modelo.items():
        if not isinstance(metricas, dict):
            continue
        custo_usd = _num(metricas.get("custo_usd"))
        if custo_usd is None:
            continue
        chamadas = _int(metricas.get("chamadas_com_uso")) or 0
        saida[str(modelo)] = round(custo_usd / max(1, chamadas), 8)
    return saida


def _normalizar_precos(precos: dict[str, Any] | None) -> dict[str, dict[str, float]]:
    if not precos:
        return {}
    saida = {}
    for modelo, valores in precos.items():
        if not isinstance(valores, dict):
            continue
        try:
            saida[str(modelo)] = {
                "in_por_1k": float(valores["in_por_1k"]),
                "out_por_1k": float(valores["out_por_1k"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
    return saida


def _item_ranking(
    modelo: str,
    metricas: dict[str, Any],
    custo: dict[str, int],
    custo_real: dict[str, float],
) -> dict[str, Any]:
    convergencia = metricas["taxa_convergencia_pos_escalada"] if metricas["escaladas"] else 1.0
    score = round(metricas["taxa_aprovacao_primeira"] - metricas["taxa_erro"] - (1.0 - convergencia), 4)
    custo_usd_por_chamada = custo_real.get(modelo)
    item = {
        "modelo": modelo,
        "score": score,
        "aprov_1a": metricas["taxa_aprovacao_primeira"],
        "taxa_erro": metricas["taxa_erro"],
        "incompletas": metricas["incompletas"],
        "taxa_incompletas": metricas["taxa_incompletas"],
        "latencia_mediana": metricas["latencia"]["mediana"],
        "amostras": metricas["verifier_julgados"],
        "_custo": custo_usd_por_chamada if custo_usd_por_chamada is not None else custo.get(modelo),
    }
    if custo_usd_por_chamada is not None:
        item["custo_usd_por_chamada"] = custo_usd_por_chamada
    return item


def _modelos_a_evitar(modelos: dict[str, dict[str, Any]], min_amostras: int, limiar_falha: float) -> list[str]:
    evitar = []
    for modelo, metricas in modelos.items():
        falha_por_chamada = (
            metricas["chamadas"] >= min_amostras
            and metricas["taxa_incompletas"] + metricas["taxa_erro"] >= limiar_falha
        )
        falha_por_qualidade = (
            metricas["verifier_julgados"] >= min_amostras
            and metricas["taxa_aprovacao_primeira"] == 0.0
        )
        if falha_por_chamada or falha_por_qualidade:
            evitar.append(modelo)
    return sorted(evitar)


def _chave_ranking(item: dict[str, Any]) -> tuple[float, float, float, str]:
    latencia = float("inf") if item["latencia_mediana"] is None else item["latencia_mediana"]
    custo = float("inf") if item["_custo"] is None else item["_custo"]
    return (-item["score"], latencia, custo, item["modelo"])


def _expandir(caminhos: list[str | Path]) -> list[Path]:
    arquivos: list[Path] = []
    for caminho in caminhos:
        path = Path(caminho)
        if path.is_dir():
            arquivos.extend(p for p in path.rglob("*.jsonl") if p.is_file())
        elif path.is_file():
            arquivos.append(path)
    return sorted(arquivos)


def _perfil_run(eventos: list[dict[str, Any]]) -> str:
    for ev in eventos:
        if ev.get("evento") == "run.perfil":
            return "rascunho" if ev.get("perfil") == "rascunho" else "certificado"
    return "certificado"


def _template_versao(ev: dict[str, Any]) -> str:
    template = _str(ev.get("template"))
    versao = _str(ev.get("versao_template"))
    if not template or not versao:
        return DESCONHECIDO
    return f"{template}@{versao}"


def _adicionar_run(
    runs: list[dict[str, Any]],
    arquivo: Path,
    indice: int,
    eventos: list[dict[str, Any]],
    incluir_rascunho: bool,
) -> None:
    perfil = _perfil_run(eventos)
    if perfil == "rascunho" and not incluir_rascunho:
        return
    runs.append(_run(arquivo, indice, eventos, perfil))


def _run(arquivo: Path, indice: int, eventos: list[dict[str, Any]], perfil: str) -> dict[str, Any]:
    return {
        "id": arquivo.name if indice == 1 else f"{arquivo.name}#{indice}",
        "fonte": str(arquivo),
        "perfil": perfil,
        "eventos": eventos,
    }


def _metricas() -> dict[str, Any]:
    return {
        "chamadas": 0,
        "respostas": 0,
        "erros": 0,
        "incompletas": 0,
        "falhas_internas": 0,
        "taxa_erro": 0.0,
        "taxa_incompletas": 0.0,
        "verifier_julgados": 0,
        "verifier_aprovados_primeira": 0,
        "taxa_aprovacao_primeira": 0.0,
        "reprovacoes": 0,
        "amostras_motivos": [],
        "escaladas": 0,
        "escaladas_convergidas": 0,
        "taxa_convergencia_pos_escalada": 0.0,
        "_latencias": [],
    }


def _metricas_custo() -> dict[str, Any]:
    return {
        "tokens_prompt": 0,
        "tokens_completion": 0,
        "tokens_total": 0,
        "tempo_total_s": 0.0,
        "chamadas_com_uso": 0,
        "_custos_usd": [],
    }


def _finalizar_metricas(metricas: dict[str, Any]) -> dict[str, Any]:
    m = dict(metricas)
    lat = m.pop("_latencias")
    m["taxa_erro"] = _ratio(m["erros"], m["chamadas"])
    m["taxa_incompletas"] = _ratio(m["incompletas"], m["chamadas"])
    m["taxa_aprovacao_primeira"] = _ratio(m["verifier_aprovados_primeira"], m["verifier_julgados"])
    m["taxa_convergencia_pos_escalada"] = _ratio(m["escaladas_convergidas"], m["escaladas"])
    m["latencia"] = {"amostras": len(lat), "mediana": _median(lat), "p90": _p90(lat)}
    return m


def _somar_custo(destino: dict[str, Any], origem: dict[str, Any]) -> None:
    destino["tokens_prompt"] += origem["tokens_prompt"]
    destino["tokens_completion"] += origem["tokens_completion"]
    destino["tokens_total"] += origem["tokens_total"]
    destino["tempo_total_s"] += origem["tempo_total_s"]
    destino["chamadas_com_uso"] += origem["chamadas_com_uso"]
    destino["_custos_usd"].extend(origem["_custos_usd"])


def _finalizar_custo(metricas: dict[str, Any]) -> dict[str, Any]:
    custos = metricas.get("_custos_usd", [])
    return {
        "tokens_prompt": int(metricas["tokens_prompt"]),
        "tokens_completion": int(metricas["tokens_completion"]),
        "tokens_total": int(metricas["tokens_total"]),
        "tempo_total_s": round(float(metricas["tempo_total_s"]), 3),
        "chamadas_com_uso": int(metricas["chamadas_com_uso"]),
        "custo_usd": None if not custos else round(float(sum(custos)), 6),
    }


def _verifier(ev: dict[str, Any]) -> bool:
    return str(ev.get("portao", "")).startswith("verifier:")


def _motivo(ev: dict[str, Any]) -> str | None:
    valor = ev.get("motivo") or ev.get("lacunas")
    if isinstance(valor, (list, dict)):
        return json.dumps(valor, ensure_ascii=False, sort_keys=True)
    return str(valor) if valor else None


def _inc2(alvo: dict[str, Any], a: str, b: str) -> None:
    alvo.setdefault(a, {})
    alvo[a][b] = alvo[a].get(b, 0) + 1


def _papel(ev: dict[str, Any]) -> str:
    return _str(ev.get("papel")) or "desconhecido"


def _str(valor: Any) -> str | None:
    return None if valor is None or str(valor) == "" else str(valor)


def _modelo_custo(ev: dict[str, Any]) -> str:
    return _str(ev.get("modelo")) or DESCONHECIDO


def _modelo_uso(ev: dict[str, Any]) -> str:
    modelo = _str(ev.get("modelo")) or DESCONHECIDO
    provedor = _str(ev.get("provedor"))
    if provedor and modelo != DESCONHECIDO and not modelo.startswith(f"{provedor}/"):
        return f"{provedor}/{modelo}"
    return modelo


def _tier(valor: Any) -> str:
    return _str(valor) or SEM_TIER


def _num(valor: Any) -> float | None:
    return float(valor) if isinstance(valor, (int, float)) else None


def _token(valor: Any) -> int:
    try:
        token = int(valor)
    except (TypeError, ValueError):
        return 0
    return max(0, token)


def _int(valor: Any) -> int | None:
    try:
        return None if isinstance(valor, bool) else int(valor)
    except (TypeError, ValueError):
        return None


def _chave_chamada(ev: dict[str, Any]) -> tuple[str, int | None]:
    return (_str(ev.get("executor")) or "desconhecido", _int(ev.get("tentativa")))


def _depois(t: float | None, marco: float | None) -> bool:
    return t is None or marco is None or t >= marco


def _delta(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else round(max(0.0, b - a), 3)


def _ratio(a: int, b: int) -> float:
    return 0.0 if b <= 0 else round(a / b, 4)


def _median(valores: list[float]) -> float | None:
    return None if not valores else round(float(statistics.median(valores)), 3)


def _p90(valores: list[float]) -> float | None:
    if not valores:
        return None
    return round(float(sorted(valores)[max(0, math.ceil(0.9 * len(valores)) - 1)]), 3)


def _ordenar_modelos(perfis: dict[str, dict[str, Any]]) -> list[str]:
    def chave(modelo: str) -> tuple[float, float, float, str]:
        m = perfis[modelo]
        mediana = m["latencia"]["mediana"]
        latencia = float("inf") if mediana is None else mediana
        return (-m["taxa_aprovacao_primeira"], m["taxa_erro"], latencia, modelo)

    return sorted(perfis, key=chave)


def _pct(valor: float) -> str:
    return f"{valor * 100:.1f}%"


def _int_md(valor: Any) -> str:
    return str(int(valor or 0))


def _seg(valor: float | None) -> str:
    return "n/d" if valor is None else f"{valor:.3f}s"


def _usd(valor: float | None) -> str:
    return "" if valor is None else f"{valor:.6f}"


def _linha_custo_total(total: dict[str, Any]) -> str:
    return (
        f"- tokens prompt {_int_md(total['tokens_prompt'])}, completion {_int_md(total['tokens_completion'])}, "
        f"total {_int_md(total['tokens_total'])}; tempo total {_seg(total['tempo_total_s'])}; "
        f"custo_usd {_usd(total['custo_usd']) or 'n/d'}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
