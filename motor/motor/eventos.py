"""Log JSONL event-sourcing — fonte da verdade auditável, independente do framework.

Formato compatível com o painel do motor v0.4: {"t": s_relativos, "evento": tipo, ...}.
O checkpointer do LangGraph cuida de resume; este log cuida de auditoria e painel.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


class LogEventos:
    def __init__(self, path: str | Path, truncar: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "w" if truncar else "a", encoding="utf-8")
        self.t0 = time.time()

    def evento(self, tipo: str, **dados) -> None:
        e = {"t": round(time.time() - self.t0, 3), "evento": tipo, **dados}
        self._f.write(json.dumps(e, ensure_ascii=False) + "\n")
        self._f.flush()

    def fechar(self) -> None:
        self._f.close()
