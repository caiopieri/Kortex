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


def carregar_runs(caminhos: list[str | Path]) -> tuple[list[dict[str, Any]], int]:
    runs, malformadas = [], 0
    for arquivo in _expandir(caminhos):
        eventos, indice, ultimo_t = [], 1, None
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
                    runs.append(_run(arquivo, indice, eventos))
                    eventos, indice = [], indice + 1
                eventos.append(ev)
                ultimo_t = t if t is not None else ultimo_t
        if eventos:
            runs.append(_run(arquivo, indice, eventos))
    return runs, malformadas


def analisar(caminhos: list[str | Path]) -> dict[str, Any]:
    runs, malformadas = carregar_runs(caminhos)
    agregador = _Agregador()
    return {
        "versao": 1,
        "fontes": sorted({run["fonte"] for run in runs}),
        "linhas_malformadas": malformadas,
        "por_papel_tier": agregador.consumir_runs(runs),
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m motor.curador",
        description="Gera perfil read-only de aptidao a partir de logs JSONL.",
    )
    parser.add_argument("caminhos", nargs="+")
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    perfil = analisar(args.caminhos)
    if args.json_path:
        args.json_path.write_text(
            json.dumps(perfil, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(formatar_markdown(perfil), end="")
    return 0


class _Agregador:
    def __init__(self) -> None:
        self.metricas: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(_metricas))

    def consumir_runs(self, runs: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        for run in runs:
            self._consumir_run(run["eventos"])
        return self._finalizar()

    def _consumir_run(self, eventos: list[dict[str, Any]]) -> None:
        chamadas: dict[tuple[str, int | None], dict[str, Any]] = {}
        ultimo_executor: dict[str, dict[str, Any]] = {}
        tier_por_papel: dict[str, str] = {}
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
                info = {
                    "executor": executor,
                    "tentativa": _int(ev.get("tentativa")),
                    "papel": _str(ev.get("papel")) or executor,
                    "tier": _tier(ev.get("tier")),
                    "t": tempo,
                }
                chamadas[(executor, info["tentativa"])] = ultimo_executor[executor] = info
                tier_por_papel[info["papel"]] = info["tier"]
                self._m(info)["chamadas"] += 1
            elif tipo in {"executor.respondeu", "executor.erro"}:
                info = chamada(ev)
                if not info:
                    self.metricas[_str(ev.get("executor")) or "desconhecido"][SEM_TIER]["erros"] += 1
                    continue
                self._m(info)["respostas" if tipo == "executor.respondeu" else "erros"] += 1
                if info["t"] is not None and tempo is not None:
                    self._m(info)["_latencias"].append(round(max(0.0, tempo - info["t"]), 3))
            elif tipo == "modelo.falha":
                papel = _str(ev.get("papel")) or "desconhecido"
                self.metricas[papel][tier_por_papel.get(papel, SEM_TIER)]["erros"] += 1
            elif tipo == "executor.escalado":
                executor = _str(ev.get("executor")) or "desconhecido"
                info = ultimo_executor.get(executor, {"papel": executor, "tier": SEM_TIER})
                origem = {"papel": info["papel"], "tier": _tier(ev.get("de") or info["tier"])}
                self._m(origem)["escaladas"] += 1
                escaladas.append({"executor": executor, "t": tempo, "origem": origem, "ok": False})
            elif tipo in {"portao.aprovado", "portao.reprovado"} and _verifier(ev):
                self._julgar(ev, tempo, ultimo_executor, escaladas)

    def _julgar(
        self,
        ev: dict[str, Any],
        tempo: float | None,
        ultimo_executor: dict[str, dict[str, Any]],
        escaladas: list[dict[str, Any]],
    ) -> None:
        executor = str(ev.get("portao", "")).split(":", 1)[1]
        info = ultimo_executor.get(executor, {"papel": executor, "tier": SEM_TIER})
        m = self._m(info)
        m["verifier_julgados"] += 1
        if ev.get("evento") == "portao.aprovado":
            m["verifier_aprovados_primeira"] += 1 if _int(ev.get("ciclo")) == 1 else 0
            for esc in escaladas:
                if esc["executor"] == executor and not esc["ok"] and _depois(tempo, esc["t"]):
                    esc["ok"] = True
                    self._m(esc["origem"])["escaladas_convergidas"] += 1
            return

        m["reprovacoes"] += 1
        motivo = _motivo(ev)
        if motivo and motivo not in m["amostras_motivos"] and len(m["amostras_motivos"]) < 3:
            m["amostras_motivos"].append(motivo)

    def _finalizar(self) -> dict[str, dict[str, dict[str, Any]]]:
        saida: dict[str, dict[str, dict[str, Any]]] = {}
        for papel in sorted(self.metricas):
            saida[papel] = {}
            for tier in sorted(self.metricas[papel]):
                m = dict(self.metricas[papel][tier])
                lat = m.pop("_latencias")
                m["taxa_erro"] = _ratio(m["erros"], m["chamadas"])
                m["taxa_aprovacao_primeira"] = _ratio(m["verifier_aprovados_primeira"], m["verifier_julgados"])
                m["taxa_convergencia_pos_escalada"] = _ratio(m["escaladas_convergidas"], m["escaladas"])
                m["latencia"] = {"amostras": len(lat), "mediana": _median(lat), "p90": _p90(lat)}
                saida[papel][tier] = m
        return saida

    def _m(self, info: dict[str, Any]) -> dict[str, Any]:
        return self.metricas[info["papel"]][info["tier"]]


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


def _expandir(caminhos: list[str | Path]) -> list[Path]:
    arquivos: list[Path] = []
    for caminho in caminhos:
        path = Path(caminho)
        if path.is_dir():
            arquivos.extend(p for p in path.rglob("*.jsonl") if p.is_file())
        elif path.is_file():
            arquivos.append(path)
    return sorted(arquivos)


def _run(arquivo: Path, indice: int, eventos: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": arquivo.name if indice == 1 else f"{arquivo.name}#{indice}", "fonte": str(arquivo), "eventos": eventos}


def _metricas() -> dict[str, Any]:
    return {
        "chamadas": 0,
        "respostas": 0,
        "erros": 0,
        "taxa_erro": 0.0,
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


def _tier(valor: Any) -> str:
    return _str(valor) or SEM_TIER


def _num(valor: Any) -> float | None:
    return float(valor) if isinstance(valor, (int, float)) else None


def _int(valor: Any) -> int | None:
    try:
        return None if isinstance(valor, bool) else int(valor)
    except (TypeError, ValueError):
        return None


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


def _pct(valor: float) -> str:
    return f"{valor * 100:.1f}%"


def _seg(valor: float | None) -> str:
    return "n/d" if valor is None else f"{valor:.3f}s"


if __name__ == "__main__":
    raise SystemExit(main())
