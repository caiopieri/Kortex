# Trava GPT-5/Codex — Fase D (2026-07-29)

**Auditor:** `codex/gpt-5.6-luna` via OmniRoute, 4 rodadas.
**Escopo:** tudo entre `8cac9af` e `1939d72` — escalada de portão + carimbo de
reprovação, sandbox de comando, rigor do curador (U-04/U-06b/U-07) e cobertura
de evidência.
**Motivo:** critério 3 da carta (`AUDITORIA-FINAL.md`) exige duas travas de
fornecedor. Todo esse trabalho tinha passado só pela trava Anthropic — que sou
eu, que o escrevi. Auditor e autor sendo o mesmo fornecedor não é auditoria.

## Resultado

9 achados reportados em 4 rodadas. **6 confirmados e corrigidos**, cada um com
reprodutor permanente. 3 rejeitados com motivo.

O padrão dos confirmados é revelador: **cinco dos seis eram a métrica de
cobertura reportando MAIS prova do que existia.** É exatamente o defeito que ela
não pode ter, já que a resposta inteira se apoia nela — e eu não o vi porque
escrevi o código convencido de que ele media o que eu queria medir.

| id | sev | achado | desfecho |
|---|---|---|---|
| C-01 | ALTA | Denominador contava NÓS, não artefatos: 1 nó coberto + 1 nó com 100 artefatos descobertos reportava "1 de 2 = 50%" onde o real era 1/101 (~1%) | corrigido |
| C-02 | ALTA | `carimbar_evidencia` lia só a spec e escrevia "passaram por portão de execução" mesmo com o validador saindo com exit 1, ou sem ele ter rodado | corrigido |
| C-03 | MEDIA | `chave=` permitia o chamador selar e certificar com chave própria, dispensando `KORTEX_CURADOR_CHAVE` | travado por teste no caminho autoritativo |
| C-04 | MEDIA | `bool(r.get("aprovado"))` — `bool("false")` é `True` | corrigido para `is True` |
| C-05 | BAIXA | TOCTOU entre `stat()` e `read_bytes()` da chave: permissão checada num inode, chave lida de outro | corrigido com `os.fstat` no próprio descritor |
| C-06 | MEDIA | Sintetizador podia escrever "Cobertura de evidência: 100 de 100…" no corpo; o carimbo real vinha depois e quem lesse a primeira ocorrência levava a forjada | corrigido (`desautorizar_imitacao`) |
| C-07 | MEDIA | `chave=` explícita pulava a regra de 32 bytes que `carregar_chave_selo` aplica | corrigido |
| C-08 | MEDIA | Modo spec-only e modo medido tinham saída idêntica; consumidor podia publicar promessa como cobertura observada | corrigido (campo `medido`) |
| C-09 | MEDIA | Id vazio virava chave-curinga: validador sem `id` casava com resultado sem `id` | corrigido |

### Rejeitados, com motivo

- **"`resultados` não é autenticado."** É estado interno do motor, produzido por
  `executar_validador`. Não é entrada de atacante; quem controla a memória do
  processo já controla tudo. Autenticar aqui seria teatro.
- **"Id repetido deixa escolher o resultado aprovado pela ordem."** Id repetido é
  RETENTATIVA, e o último veredito vencer é o certo — nó que reprovou e passou na
  retentativa está coberto. A ordem vem do append cronológico do motor, não de
  fora. Semântica agora fixada em teste nos dois sentidos.
- **"Missão sem artefato não recebe carimbo."** Decisão deliberada, re-reportada
  duas vezes. Carimbar missão de texto treina o leitor a ignorar o carimbo, e o
  de reprovação vai junto quando isso acontece.

## Aceito em aberto (não corrigido)

**O `runner` injetado em `rodar_sombra` não é autenticado.** Nada prova que ele
chamou um modelo de verdade; `runner_executa_modelo` é uma declaração do
chamador. É o resíduo de U-04: consertei "o titular vem do arquivo", não "o
runner é confiável".

Não corrigi porque não dá para autenticar um callback de dentro do mesmo
processo, e qualquer atestado que eu inventasse seria forjável pelo mesmo
caminho — protetor de mentira, que é pior que buraco conhecido. **A correção real
é amarrar cada resultado de sombra a uso medido no ledger de orçamento**
(`_LedgerCusto`), que é a mesma ponta solta que a auditoria Anthropic apontou em
U-04. Vira tarefa própria.

Atenuante factual: **não existe runner de produção wired hoje.** O único runner
da CLI marca `sombra_simulada`, que a certificação recusa. Ou seja, nada consegue
ser certificado em produção neste momento — o buraco é sobre o componente que
ainda vai existir, não sobre um caminho vivo.

## Quando parei, e por quê

Quatro rodadas. Na quarta, dois dos quatro "achados" eram re-report de decisões
que eu já havia declarado, e um era inalcançável pelo caminho normal (a spec
rejeita id vazio). Rendimento caindo para re-report é o sinal de saturação — de
lá em diante o auditor produz achado porque foi pedido achado, não porque achou.

Corrigi mesmo os inalcançáveis quando o custo era uma linha (C-09): defesa barata
contra caminho futuro é diferente de teatro.

### Onde isto pode dar errado

- **Um auditor, um modelo, um prompt.** Fronteira dupla é sobre fornecedor, e
  isso eu tenho — mas não é sobre cobertura. Um segundo prompt, ou o mesmo modelo
  com o código inteiro em vez do diff, acharia outras coisas. "Sem achado ≥ média
  na quarta rodada" não é "sem defeito".
- **O auditor viu diff e trechos, não o repositório.** Área 2 (sandbox) voltou
  "nenhum achado" nas quatro rodadas, e na quarta ele mesmo disse que não havia
  implementação de `compor_sandbox` no material enviado. Isso é ausência de
  evidência, não evidência de ausência — o sandbox segue coberto só pela suíte
  causal e pela trava Anthropic.
- **Eu triei meus próprios achados.** Rejeitei três, e a justificativa é minha.
  Se eu estiver errado sobre `resultados` ser fronteira interna, o C-01 de amanhã
  vem daí.
- **Os reprodutores de C-01/C-02 travam o sintoma, não a classe.** A classe é
  "métrica lê configuração e afirma resultado". Nada impede a próxima métrica de
  repetir o padrão num lugar novo.
