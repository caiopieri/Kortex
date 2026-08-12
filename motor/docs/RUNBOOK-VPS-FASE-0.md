# RUNBOOK — Fase 0: Kortex 24/7 em VPS ARM (Oracle)

Objetivo da fase: **a VPS de pé e provada, sem rodar missão nenhuma.** Missão é Fase 1
em diante. Se a Fase 0 terminar com `pytest` verde e o sandbox conforme, ela cumpriu.

Regime permanente é o **always-free**. Crédito é para rajada que vira artefato
permanente, nunca para manter o sistema de pé — o que roda em shape pago morre no
dia 31.

---

## 0. O que já foi provado daqui (não repetir na VPS)

Verificado em 2026-08-11, antes da VPS existir:

- A base do sandbox (`python@sha256:6771159c…`) é um **índice OCI multi-arch** e inclui
  `linux/arm64/v8`. O `FROM` por digest continua valendo no ARM.
- A imagem do sandbox **builda limpa em arm64**: os 10 pins de `sandbox/requirements.txt`
  têm wheel aarch64 e o `compileall` do Dockerfile passou (ele falha o build se alguma
  dependência vier quebrada).
- A imagem arm64 **executa**: a suíte gerada em `runs/ebay-q-neg-01/artefatos` roda
  dentro dela com `--network none --read-only`, em `aarch64`, `16 passed`.

Ou seja: ARM não é risco. É só rebuildar lá e re-pinar o digest.

---

## 1. Conta Oracle

- Região: escolher uma com capacidade de `VM.Standard.A1.Flex`. "Out of capacity" no
  Ampere é crônico; se a primeira falhar, tentar outra região **antes** de mudar o plano.
- Shape: `VM.Standard.A1.Flex`, ARM.
- **Teto always-free desde 15/jun/2026: 1.500 OCPU-horas + 9.000 GB-horas por mês**,
  equivalente a **2 OCPU / 12 GB rodando 24/7**. Era 4/24 até essa data; a Oracle cortou
  pela metade sem anúncio. Conferir o número real na console da própria tenancy.
- SO: **Ubuntu 24.04 LTS (aarch64)**.

### ⚠️ Budget da OCI ALERTA, não bloqueia

`Billing → Budgets` dispara notificação ao cruzar o limite. **Não desliga recurso e não
impede gasto.** Um teto de US$300 configurado ali não é um teto: é um aviso.

Para não gastar de verdade depois dos créditos, a contenção tem que ser operacional:

1. Manter tudo **dentro** do always-free como estado normal — assim o gasto base é zero,
   e só rajada deliberada gera custo.
2. Toda instância acima do always-free nasce com **data de morte anotada** e é destruída
   por decisão, não por esquecimento.
3. Budget alert em 50% / 80% / 100% como rede de segurança, sabendo que é só aviso.

---

## 2. Host

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.13 python3.13-venv git docker.io
sudo usermod -aG docker $USER   # relogar depois
```

**Python 3.13, não 3.14.** `pyproject.toml` declara `requires-python = ">=3.10,<3.14"`
porque `langchain_core` ainda importa `pydantic.v1`, que não é compatível com 3.14. Todo
o trabalho de 2026-08-11 rodou em 3.14 e funcionou, mas fora do contrato — na VPS não há
motivo para repetir isso.

**Docker no host, Kortex fora de container.** Não é preferência:
`specs/001-hardening-producao/sandbox-conformance.md` requisito 3 proíbe mount de socket
do engine. Kortex dentro de container precisaria de Docker-in-Docker para abrir o
sandbox, ou seja, montar o socket — o motor violaria a spec que ele existe para
certificar.

---

## 3. Imagem do sandbox

```bash
cd ~/Kortex/motor
docker build -t kortex/sandbox:arm64 sandbox/
docker image inspect kortex/sandbox:arm64 --format '{{.Id}} {{.Architecture}}'
```

O digest sai **diferente** do amd64 (`a58d4e0c…`). Isso é esperado e importante:
**arquitetura diferente é identidade de evidência diferente**, não substituição.

Criar `exemplos/sandbox-kortex-arm64.json` com o digest novo. **Não sobrescrever**
`sandbox-kortex.json` — mesma lição de `sandbox-python.json`: o nome do arquivo tem que
continuar dizendo a verdade sobre o que ele aponta.

---

## 4. OmniRoute — o obstáculo não-óbvio

`omniroute` (npm, 3.8.49) declara só `engines.node`, sem restrição de `os`/`cpu`: roda em
linux-arm64. Node ≥ 22.22.2.

O problema **não** é portabilidade, é credencial. Os provedores que o Kortex usa hoje
(`claude`, `codex`, `agy`) são `auth_type: oauth` — sessões de navegador. Numa VPS
headless não há navegador. Dois caminhos, e é decisão do fundador:

- **Túnel SSH** (`ssh -L`) para completar o fluxo OAuth a partir do laptop, uma vez por
  provedor. Mais limpo; sessões nascem na VPS.
- **Copiar `~/.omniroute/storage.sqlite`** do Mac. Mais rápido, mas carrega tokens entre
  máquinas e depende de `STORAGE_ENCRYPTION_KEY` — verificar se a chave é derivada da
  máquina antes de contar com isso.

Enquanto o OmniRoute só existir numa máquina, ele é **ponto único de falha** do Kortex.
Registrar como risco, não resolver na Fase 0.

---

## 5. Gate da Fase 0

A fase só fecha com os três:

1. `python3 -m pytest tests/ -q` na VPS → 6 falhas conhecidas (A-03/A-04/A-05 e
   E-01/E-02/E-03 da auditoria Anthropic), nenhuma nova.
2. Preflight de sandbox aceitando o digest arm64 novo, com a evidência impressa
   (`engine_version os_type policy_version digest`).
3. **A execução real de `sandbox-conformance` num Linux dedicado.** É a primeira vez que
   isso é possível: no macOS o preflight passava mas o próprio código anota que Docker
   Desktop **não é** o runner que a spec exige. Toda evidência de execução produzida até
   hoje tem essa ressalva. A VPS a remove.

Rodar suíte completa **um de cada vez**: `main()` escreve em `log.jsonl` na raiz do repo
sob flock exclusivo, então duas suítes simultâneas se contaminam e produzem conjuntos de
falha diferentes. Isso é dívida aberta (ver Fase 2).

---

## Fica aberto para as fases seguintes

- **Fase 1 — moeda de contenção para rota grátis.** `PRECOS` em `omniroute_orcado.py` tem
  19 modelos code-owned; `modelo sem preco declarado` reprova fechado. NVIDIA, DeepSeek,
  GLM, Gemini free e Alibaba não rodam hoje. Cadastrar preço zero seria pior que o
  bloqueio: silencia a única contenção que o motor tem. Rota grátis precisa ser governada
  por **cota e disponibilidade**, não por BRL.
- **Fase 2 — serviço, não CLI.** Duas missões de CLI não coexistem (flock no `log.jsonl`
  da raiz). `GerenciadorJobs` já usa log por job e é o entrypoint certo para 24/7. Mover
  o log da CLI quebra `motor_painel/painel.py`, que lê `BASE.parent / "log.jsonl"`
  hardcoded — decisão do fundador, e a branch atual é a da refatoração do painel.
- **Fase 3 — calibração de provedor por evidência.** Mesma missão em Claude, grátis-bom e
  grátis-fraco, comparada por portão de processo e AST. É o melhor uso do crédito: paralelo,
  faminto de CPU, e o produto é uma tabela permanente.
- **Fase 4 — scraping com rotação de proxy, GPU para fine-tune.** Só depois das três.

## Divisão de responsabilidade que não muda

- **Disponibilidade é do OmniRoute.** Ele já tem `domain_circuit_breakers`, `quota_pools`,
  `provider_key_limits`, `rate_limit_overrides_json`. O Kortex não tem nenhuma lógica de
  saúde de provedor, e não deve ganhar: "caiu, vai pro próximo" é trabalho do gateway.
- **Qualidade é do Kortex**, e ele sabe medir: rubrica, verifier, evaluator, portão de
  processo executando e comparação por AST. Trocar de provedor deixa de ser fé e vira
  experimento.
