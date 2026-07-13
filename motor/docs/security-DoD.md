# Security Definition of Done — motor

Este checklist define evidência mínima por mudança. Ele não certifica sozinho um build,
deployment, sandbox ou backend. Marque cada item como `atendido`, `bloqueado` ou `N/A` e
registre comando, teste ou justificativa; não transforme ausência de controle em `N/A`.

## Universal

- [ ] Escopo, fronteiras de confiança e ativos afetados estão identificados.
- [ ] Input externo falha fechado, sem coerção silenciosa, fallback permissivo ou default
  com autoridade maior.
- [ ] Erro parcial preserva evidência, não confirma estado ambíguo e não expõe segredo,
  prompt, stack ou dado pessoal.
- [ ] Privilégio, acesso a filesystem/rede e mutações são os mínimos necessários.
- [ ] Caminho feliz, limite e caso hostil possuem teste causal.

## Input externo

- [ ] Schema fecha tipos, campos obrigatórios, enumerações, tamanho e valores finitos antes
  de qualquer efeito.
- [ ] IDs, paths e nomes rejeitam controles, traversal, symlink/hardlink indevido e aliases
  ambíguos quando atravessam fronteira operacional.
- [ ] JSON/eventos validam envelope e payload; dado legado de leitura não ganha autoridade
  de escrita ou decisão.
- [ ] Comando é `argv` tipado, sem shell; identidade executável é absoluta e allowlisted.

## Ambiente e autonomia

- [ ] Autonomia não executa subprocesso no host. Sem runner explicitamente composto, o
  comportamento é negar.
- [ ] Backend de comando foi certificado para o deployment: imagem por digest, rootfs RO,
  somente workspace RW, rede desligada, env por allowlist, usuário não-root, capabilities
  removidas, `no-new-privileges` e limite de PIDs.
- [ ] Timeout, output combinado e árvore de processos possuem limites e cleanup causalmente
  testados em sucesso, erro, overflow e TERM/KILL.
- [ ] Fake/local runner está restrito a testes/dev e nunca é usado como prova de sandbox.

## Bot e LLM

- [ ] Missão, saída de modelo, artefato recuperado e mensagem externa são dados, nunca
  instrução confiável ou permissão.
- [ ] Veredito e decisão usam domínio tipado; texto livre, truthiness e status
  auto-declarado não atravessam gates.
- [ ] Gate sensível não é auto-respondido por modelo, `auto_mode`, override ou default.
- [ ] Ação relevante passa por validador/gate e emite evento sanitizado e schema-validado.

## Persistência e concorrência

- [ ] Escrita concorrente usa transação/lock e transição CAS onde aplicável.
- [ ] Crash boundaries foram testadas antes e depois de persistir efeito, ack ou arquivo.
- [ ] Entrega at-least-once usa chave idempotente durável; documentação não promete
  exactly-once entre stores sem protocolo que o prove.
- [ ] Lease, deadline e relógio usados estão explícitos; expiração permite recovery seguro.
- [ ] Lifecycle fecha workers, locks, conexões e arquivos de modo verificável.

## Secrets e análise estática

- [ ] Credenciais não entram no repositório, log, artefato, exception ou imagem.
- [ ] Variáveis de ambiente são allowlisted na fronteira externa; herança integral é vetada.
- [ ] Ruff, mypy, Bandit high/high, Gitleaks e `compileall` rodam no diff/snapshot aplicável.
- [ ] Dependências, imagem e policy operacionais têm versão imutável ou digest registrado.

## Gates e `N/A`

- [ ] Pytest da fatia e suíte consolidada passam sem `skip`, `xfail`, remoção ou relaxamento
  de teste não autorizado.
- [ ] Build/install e smoke test usam o snapshot que será entregue; checkout sujo não é
  artefato de release.
- [ ] Gate externo de CI permanece separado dos testes unitários do runner.
- [ ] Cada `N/A` nomeia a fronteira ausente e explica por que a mudança não pode alcançá-la.
- [ ] Item bloqueado permanece dívida explícita e impede a alegação correspondente, sem
  impedir componentes default-deny independentes quando isso estiver documentado.
