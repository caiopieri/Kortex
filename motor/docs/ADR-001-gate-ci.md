# ADR-001: Implementação do Gate de CI na Meta-Fábrica

## Status
Parcialmente implementado. Gate externo ativo; capacidade de comando no motor indisponível
sem backend H05b certificado.

## Contexto
Atualmente, a qualidade das entregas de software do motor v0.5 e do próprio monorepo é "auto-reportada" pelo agente, o que representa a maior lacuna de qualidade. A teoria do `dev-harness` (Fase 4, passo 1) e o `ROADMAP.md` exigem um portão de verificação externo e determinístico ("a máquina decide, o agente propõe"). 

Além disso, a arquitetura do motor possui "validadores determinísticos (V1)" restritos aos tipos `schema_json` e `contem`. No entanto, para missões de engenharia de software (como no `dev-harness`), precisamos validar o código gerado em tempo de execução rodando ferramentas reais (como linters, type-checkers e suítes de testes), fornecendo feedback de erro acionável para o loop de auto-correção (Fase C / reconciliação na fonte).

## Decisão
Decidimos dividir a implementação do **Gate de CI** em duas camadas integradas, respeitando os princípios de "músculo, não autoridade", YAGNI e a preservação do grafo LangGraph fixo:

### 1. Gate Externo de CI (GitHub Actions)
Adicionaremos um pipeline de CI executado no GitHub Actions a cada Pull Request e push na branch `main`. Este pipeline rodará em máquina neutra e garantirá os seguintes jobs:
* **lint:** `ruff check` (ou similar)
* **type-check:** `mypy`
* **test:** `pytest` (com cobertura como sinal)
* **sast:** `bandit` / `semgrep`
* **secrets:** `gitleaks` (ou similar)
* **build:** `pip install -e .`

O merge na `main` será bloqueado caso qualquer job falhe.

### 2. Nó Validador Determinístico de `comando` (LangGraph / WorkflowSpec)
Estenderemos a `WorkflowSpec v0.1` e a lógica de execução no `grafo.py` para introduzir o validador de tipo `comando`.

* **Gramática da Spec:** Um nó validador pode agora declarar `kind: "comando"` com a configuração do executável a ser rodado (ex: `pytest`, `ruff check`).
  ```json
  {
    "id": "valida-codigo",
    "tipo": "validador",
    "valida": "programador",
    "validador": {
      "kind": "comando",
      "config": {
        "comando": "pytest {caminho_teste}",
        "timeout": 30
      }
    },
    "entradas": {
      "caminho_teste": {
        "ref_artefato": {
          "de": "programador",
          "nome": "test_app.py"
        }
      }
    },
    "depende_de": ["programador"]
  }
  ```
* **Mecânica no LangGraph:**
  1. O nó `validador` de tipo `comando` lerá a entrada resolvida (via `resolver_refs_artefato`).
  2. Validará identidade absoluta do executável, allowlist e argumentos tipados antes da
     fronteira de execução.
  3. Delegará um `CommandRequest` a um `CommandRunner` injetado. O default é
     `DenyCommandRunner`: nenhum subprocesso local é fallback de produção.
  4. Somente um backend certificado poderá interpretar exit code `0` como **aprovado**;
     indisponibilidade, timeout ou código diferente de zero reprovam.
  5. O validador retornará `refazer: alvo` (apontando para o nó `programador`).
  6. Se reprovado, o loop de auto-correção (Fase C) reiniciará o nó `programador` passando
     feedback limitado como contexto para correção.

### Por que esta abordagem?
* **Sem novas topologias:** Não cria nós novos no grafo LangGraph. O grafo fixo continua intacto; adiciona-se apenas capacidade interpretativa ao nó validador (dado, não código).
* **Compatível com a Reconciliação:** O uso do nó `validador` (em vez de um nó `ferramenta` genérico) garante que a relação `"refazer"` aponte para o nó que produziu o erro. Se usássemos nós de ferramenta comuns, o motor não saberia qual nó modelo reexecutar a montante.
* **Emissão de Eventos:** O resultado do validador emite `validador.rodou` no stream de eventos, permitindo auditoria e visualização em tempo real na interface viva.

## Consequências
* **Positivas:**
  * Qualidade enforçada por máquina no repositório pelo gate externo.
  * No motor, validação e composição falham fechado quando não existe executor certificado.
  * Relação determinística limpa e rastreável no log de eventos.
* **Riscos / Mitigações:**
  * *CI Flaky/Lento:* Para o repositório, o tempo total do CI deve ser medido para garantir que rode em `< 5 min`. Usaremos cache de dependências no GitHub Actions.
  * *Falsa certificação por `cwd`:* tempdir não isola filesystem, ambiente, rede ou árvore de
    processos. C2/C3 só podem ser habilitados por adapter, policy, imagem por digest e job de
    conformidade descritos em `../specs/001-hardening-producao/verification-h05b.md`.

## Plano de Handoffs (Fatiamento)
Fatiamos a entrega para o Operário nos seguintes commits atômicos:
1. **Handoff 01 (Monorepo CI):** Criar `.github/workflows/ci.yml` configurando os jobs (lint, type-check, tests, build) rodando em GitHub Actions.
2. **Handoff 02 (Validador Spec):** Modificar `motor/spec.py` para permitir `kind: "comando"` na validação de `WorkflowSpec`.
3. **Handoff 03 (Motor Runner):** Separar protocolo e backend, manter default-deny e integrar
   resultado tipado ao loop de reconciliação.
4. **Handoff 04 (Testes do Motor):** Cobrir contrato unitário com fake explicitamente
   injetado; estes testes não certificam sandbox.
5. **Handoff 05 (Deployment H05b):** Certificar adapter, engine, policy e imagem em job real.
   Enquanto faltar, `kind:"comando"` permanece indisponível em produção.
