"""Caixa do fundador — gate humano durável via nota no vault (formato do v0.4).

Quando o grafo chega a `interrupt()` (cobertura reprovada), o motor não pode
decidir sozinho: escala ao fundador escrevendo uma nota Markdown na caixa e
faz *poll* da linha `decisao:` do frontmatter até o humano responder.

Durabilidade tem duas camadas independentes:
- o **checkpointer** (SQLite) segura o estado do grafo no ponto do interrupt, de
  modo que `rodar_com_caixa` pode ser religado após um crash e retomar;
- a **nota** é a interface humana e também é durável: uma nota `PENDENTE` que
  sobrevive ao crash é *reaproveitada* (evento `decisao.retomada`), não recriada.

Espelha `caixa_fundador` do motor v0.4 (vault, `5. Motor v0/motor.py`): mesmo
frontmatter (`estado/portao/criada/decisao`), mesmo corpo (Pergunta/Contexto/
Opções), mesmos eventos (`decisao.pendente/.retomada/.fundador/.timeout`) e o
mesmo renomear para `decidida <timestamp> — <portao>.md` ao concluir.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Optional, cast

from langgraph.types import Command

# captura a 1ª linha não-vazia do valor de `decisao:` no frontmatter
_RE_DECISAO = re.compile(r"^decisao:[ \t]*(\S.*)$", re.M)


class CaixaFundador:
    """Gate humano durável por nota no diretório `dir_caixa`.

    A decisão é dada editando a linha `decisao:` do frontmatter da nota e
    salvando. `poll_s` e `timeout_s` são configuráveis: o vault no iCloud tem
    latência de sync, então em produção convém `poll_s >= 5`; nos testes usamos
    valores pequenos com uma decisão escrita previamente (ou por thread).
    """

    def __init__(self, dir_caixa: str | Path, log: Any,
                 timeout_s: int = 600, poll_s: int = 5):
        self.dir_caixa = Path(dir_caixa)
        self.log = log
        self.timeout_s = timeout_s
        self.poll_s = poll_s

    def _nota_path(self, portao: str) -> Path:
        return self.dir_caixa / f"PENDENTE — {portao}.md"

    def escrever_nota(self, portao: str, pergunta: str,
                      contexto: str, opcoes: str) -> Path:
        """Cria a nota `PENDENTE — <portao>.md` se não existir.

        Se já existir (motor religado após crash com gate pendente), NÃO
        sobrescreve — emite `decisao.retomada` e reaproveita a nota intacta,
        preservando o que o humano já tenha digitado.
        """
        self.dir_caixa.mkdir(parents=True, exist_ok=True)
        path = self._nota_path(portao)
        if path.exists():
            self.log.evento("decisao.retomada", portao=portao, nota=path.name)
            return path
        path.write_text(
            "---\n"
            "estado: pendente\n"
            f"portao: {portao}\n"
            f"criada: {time.strftime('%Y-%m-%d %H:%M')}\n"
            "decisao: \n"
            "---\n"
            "# Decisão aguardando o fundador\n"
            "\n"
            f"**Pergunta:** {pergunta}\n"
            "\n"
            f"**Contexto:** {contexto}\n"
            "\n"
            f"**Opções:** {opcoes}\n"
            "\n"
            f"> Escreva sua decisão na linha `decisao:` do frontmatter acima e "
            f"salve. O motor verifica a cada {self.poll_s}s (prazo: {self.timeout_s}s).\n",
            encoding="utf-8",
        )
        self.log.evento("decisao.pendente", portao=portao, nota=path.name)
        return path

    def ler_decisao(self, portao: str) -> Optional[str]:
        """Lê a decisão da nota sem bloquear. None se ainda não decidida."""
        path = self._nota_path(portao)
        if not path.exists():
            return None
        m = _RE_DECISAO.search(path.read_text(encoding="utf-8"))
        if m and m.group(1).strip():
            return m.group(1).strip()
        return None

    def aguardar_decisao(self, portao: str) -> str:
        """Faz poll da nota até decidir; ao decidir, arquiva e retorna a decisão.

        Timeout → evento `decisao.timeout` + RuntimeError (a nota é mantida na
        caixa para o humano ainda poder decidir/depurar).
        """
        path = self._nota_path(portao)
        fim = time.time() + self.timeout_s
        while True:
            decisao = self.ler_decisao(portao)
            if decisao is not None:
                self.log.evento("decisao.fundador", portao=portao, decisao=decisao)
                self._arquivar(path, portao)
                return decisao
            if time.time() >= fim:
                self.log.evento("decisao.timeout", portao=portao, prazo_s=self.timeout_s)
                raise RuntimeError(
                    f"fundador não decidiu '{portao}' no prazo — nota mantida na caixa"
                )
            time.sleep(self.poll_s)

    def _arquivar(self, path: Path, portao: str) -> None:
        novo = self.dir_caixa / f"decidida {time.strftime('%Y%m%d-%H%M%S')} — {portao}.md"
        path.replace(novo)


def rodar_com_caixa(grafo, entrada, config, caixa: CaixaFundador, log: Any) -> dict:
    """Invoca o grafo; em cada interrupt escala ao fundador via nota e retoma.

    `entrada` pode ser a entrada inicial (dict) ou já um `Command` (resume).
    Enquanto o resultado contiver `__interrupt__`, escreve/reaproveita a nota
    com o payload do interrupt (portao/pergunta/lacunas/opcoes), aguarda a
    decisão humana e retoma com `Command(resume=decisao)`. Retorna o estado
    final (sem `__interrupt__`).
    """
    resultado = grafo.invoke(entrada, config)
    while "__interrupt__" in resultado:
        pedido = resultado["__interrupt__"][0].value
        portao = pedido.get("portao", "decisao")
        lacunas = pedido.get("lacunas", [])
        contexto = "; ".join(str(lac) for lac in lacunas) if lacunas else "(sem lacunas detalhadas)"
        caixa.escrever_nota(
            portao=portao,
            pergunta=pedido.get("pergunta", "Decisão necessária."),
            contexto=contexto,
            opcoes=pedido.get("opcoes", ""),
        )
        decisao = caixa.aguardar_decisao(portao)
        resultado = grafo.invoke(Command(resume=decisao), config)
    return cast(dict[Any, Any], resultado)
