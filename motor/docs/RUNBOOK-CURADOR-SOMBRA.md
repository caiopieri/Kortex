# Runbook: Curador Sombra e Certificacao

Este caminho e read-only. Ele gera evidencia diagnostica; nao muda catalogo, config ou
roteamento e nao cria intencao autoritativa de promocao.

O formato da CLI ainda e beta: artefatos JSON sao contrato interno de inspecao, nao API
publica, registro autoritativo ou entrada confiavel para apply.

## Casos held-out

Arquivo para `--sombra`:

```json
{
  "proposta": {"slot": "executor/simples", "titular": "modelo-atual", "candidato": "modelo-novo"},
  "casos": [
    {
      "id": "caso-1",
      "slot": "executor/simples",
      "entrada": {"prompt": "..."},
      "titular": {"modelo": "modelo-atual", "aprovado": true, "custo_usd": 0.02},
      "candidato": {"aprovado": true, "custo_usd": 0.01, "motivo": "ok"}
    }
  ]
}
```

`candidato` e usado apenas pelo runner stub da CLI para evitar chamada real de LLM. Adaptadores reais
devem continuar injetados por codigo/teste ate existir contrato de replay fiel.

Os casos fornecidos a `--sombra` devem ser held-out e certificados. O filtro de `rascunho` vale para o
caminho de logs (`python3 -m motor.curador <logs.jsonl>`), mas nao consegue inferir a procedencia de um
JSON manual.

## Comandos

```bash
python3 -m motor.curador --sombra casos.json --json evidencia-sombra.json
python3 -m motor.curador --certificar evidencia-sombra.json --json certificacao.json
```

`python3 -m motor.curador <logs.jsonl>` continua sendo o caminho existente de perfil read-only.

`--certificar` recomputa e sela a evidencia, mas o arquivo exportado continua nao
autoritativo. Nao promova copiando `status`, hash ou conteudo desse JSON.

O comando legado abaixo exercita somente o default-deny da CLI:

```bash
python3 -m motor.curador --promocao certificacao.json --json veto.json
```

Sem `RepositorioCertificacoes`, ele nao pode criar `promocao_pendente`. A trilha
operacional exige uma integracao de deployment que:

1. registre a certificacao validada em repositório imutavel/autenticado;
2. passe somente o `certification_id` a `preparar_promocao_gated(...)`;
3. confira que o retorno e `promocao_pendente` e `requer_gate=True`;
4. encaminhe a intencao ao gate humano; o curador nao aplica catalogo.

Este repositorio define o protocolo, mas nao fornece hoje esse backend. Portanto, promocao
operacional esta indisponivel por default; um fake de teste nao remove essa restricao.

## Chave do selo (obrigatoria para certificar)

A evidencia de sombra e selada com HMAC. Sem chave, `certificar_sombra` recusa
tudo -- de proposito: maquina sem chave configurada e o estado default, e
degradar para "selo dispensado" ali reintroduziria o defeito inteiro.

```sh
umask 077
head -c 64 /dev/urandom > ~/.config/kortex/curador.key
export KORTEX_CURADOR_CHAVE=~/.config/kortex/curador.key   # o CAMINHO, nao a chave
```

A chave em si nunca entra em variavel de ambiente: ambiente vaza em `ps`, em dump
de crash e em log de subprocesso. Arquivo legivel por grupo/outros, ou com menos
de 32 bytes, e recusado como se nao existisse.

**O que o selo protege, dito sem enfeite:** evidencia que chega de fora -- outra
maquina, diretorio de runs compartilhado, arquivo escrito por um modelo -- nao
certifica. Esse e o caminho real do flywheel e era o que passava.
**O que ele nao protege:** quem ja executa como voce nesta maquina le a chave e
forja o selo. Fechar isso exige separar o processo que produz evidencia do que a
assina, e essa separacao nao existe hoje.

## Tamanho de amostra

Piso de **30 casos held-out** (`PISO_CASOS`), no codigo e nao na politica -- o
proponente nao escolhe o proprio rigor. A vantagem de qualidade precisa passar no
**McNemar exato unilateral com p < 0.05**; com menos de 5 discordancias nenhum
placar alcanca isso, nem o perfeito. Custo continua sendo `<` estrito, porque vem
de tabela de preco por token e nao de amostra.

## Invariantes

- `motivo_certificacao` e texto opaco para auditoria/display; nao use regex nele como contrato.
- `requer_gate=True` deve ser honrado por qualquer camada que aplique mudanca real.
- `curador.promoveu` nao e emitido por estes comandos; ele pertence ao gate externo que aplicar a
  promocao.
- Custo ausente (`null`/`None`) nao e zero.
- JSON/CLI, dict, hash e `status="certificado"` fornecidos pelo chamador nao sao autoridade.
- Custo menor nunca compensa qualidade pior ou indistinguivel de sorte; os dois eixos precisam
  melhorar, qualidade com significancia e custo de forma estrita.
- Titular e candidato sao os dois MEDIDOS no mesmo runner e nos mesmos casos. Resultado de
  titular declarado no arquivo de entrada e ignorado.

## Falhas operacionais

- Repositorio ausente, ID desconhecido ou registro divergente: veto; nao contornar pela CLI.
- Evidencia selada invalida, caso duplicado, proveniencia vazia ou custo nao finito: rejeicao;
  corrigir a origem, nao o agregado.
- Runner falha em um caso: o caso registra falha e os demais continuam; revisar antes de
  certificar.
