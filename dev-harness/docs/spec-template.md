# Spec — [nome da feature]

> Copie este arquivo para `docs/specs/<feature>.md` e preencha antes de `/research`.
> A spec é a fonte da verdade. Quando o requisito mudar, edite a spec — não improvise no código.

## Problema
Que dor real isto resolve? (1-3 frases. Se você não consegue escrever, ainda não entendeu o problema.)

## Objetivo
O resultado desejado, observável. Como um usuário percebe que isto funciona?

## Escopo — dentro
- ...

## Escopo — fora (explícito)
> Esta seção é tão importante quanto a de cima. É o que impede o agente de inflar a tarefa.
- ...

## Critérios de aceite
- [ ] ... (verificáveis: "X acontece quando Y", não "funciona bem")

## Fronteiras (boundaries)
> O ponto fraco nº1 das tarefas mal-feitas. Seja explícito:
- **Entradas:** o que entra, em que formato/contrato.
- **Saídas:** o que sai, em que formato/contrato.
- **Migrations de banco:** quem/o que as faz, e em que ordem (nunca deixe ambíguo).
- **Dependências:** o que esta tarefa pressupõe pronto antes de começar.

## Restrições
- **Arquitetura:** o que NÃO pode mudar.
- **Segurança:** quais seções de `docs/security-DoD.md` se aplicam.
- **API:** se toca endpoint, anexe/atualize a spec OpenAPI — é contexto de alta alavancagem para o agente gerar o backend certo.
- **Tamanho:** PR-alvo ≤ ~300 linhas. Se a spec implica mais, quebre em tarefas.

## Não-objetivos
O que esta feature deliberadamente **não** tenta fazer (evita scope creep e expectativa errada).

## Onde isto pode dar errado
Riscos conhecidos antes de começar. Suposições que, se falsas, mudam tudo.
