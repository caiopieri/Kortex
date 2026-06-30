# Segurança — Definition of Done (multi-stack)

> A IA otimiza para "funciona"; segurança conflita com isso, e código de IA tem ~2-3x mais densidade de vulnerabilidade — **a menos que** seja exigida explicitamente. Prompting de segurança vira 6/10 em 10/10 seguro. Por isso é gate, não sugestão.
> Aplique a seção **Universal** sempre; some as seções por stack que o projeto usar (marcadas no `AGENTS.md` do repo).

## Universal (toda PR que toca lógica)
- [ ] **Validação de input** na entrada — nada de fora é confiável (form, query, header, body, upload).
- [ ] **Autorização** checada em cada endpoint que lê/altera dado — não só autenticação. (Causa nº1 de vazamento real em apps de IA: endpoint devolvendo dado sem checar permissão.)
- [ ] **Sem segredos no código** — chaves/tokens/conexões em variável de ambiente.
- [ ] **Erros não vazam interno** — sem stack trace, schema ou query na resposta ao cliente.
- [ ] **Sem injeção** — queries parametrizadas, nunca string concatenada (SQL, comando, path).
- [ ] Rodou SAST/scanner antes do merge — não só linter.

## Ambiente / autonomia (sempre que o agente executa comandos)
- [ ] Agente autônomo roda em **dev container / sandbox**, nunca solto na máquina. Isola o ambiente — não confie em travar a ferramenta (restrição de tool no skill não é imposta de forma confiável).
- [ ] Sem credenciais de produção no ambiente do agente.

## Banco / Postgres / Supabase
> Incidente real (CVE-2025-48757): schemas Supabase gerados **sem Row Level Security** expuseram 170+ apps. O agente esquece RLS porque o código funciona sem ela.
- [ ] **RLS ligada em toda tabela** com dado de usuário/operação. Tabela sem RLS é tabela pública.
- [ ] **Policies escritas e testadas** — usuário A não lê/edita dado do usuário B.
- [ ] Chave `service_role` **nunca** no cliente (front, app, bot). Só no servidor.
- [ ] Migração revisada: o que era confiado à aplicação agora precisa de policy no banco.

## Web / e-commerce / pagamentos
- [ ] **Preço e total validados no servidor** — nunca confie no valor vindo do cliente.
- [ ] **Dados de cartão nunca armazenados crus** — use processador PCI-compliant (tokenização). Você não quer PCI no seu escopo.
- [ ] CSRF em ações que mudam estado; cookies `HttpOnly` + `Secure` + `SameSite`.
- [ ] Controle de acesso a pedidos/dados de cliente (um usuário não vê pedido de outro). Atenção à LGPD.

## Mobile / iOS
- [ ] **Segredos no Keychain**, nunca no binário, `Info.plist` ou código. Binário de app é inspecionável.
- [ ] **Validação sempre no servidor** — o cliente (app) é não-confiável, mesmo sendo "seu".
- [ ] HTTPS/ATS obrigatório; sem exceções de transporte inseguro.
- [ ] Dado sensível fora de logs, cache e screenshots de background.

## Bot / entrada de LLM (parsing de foto/texto, agentes)
> Conteúdo de terceiro é superfície de prompt injection; injeção indireta tem sucesso 20-30% maior, e CVEs de IA agêntica cresceram 255% no último ano.
- [ ] Texto/foto recebidos são **dado, nunca instrução** ao modelo.
- [ ] Saída do modelo é **validada e tipada** antes de tocar o banco — nunca executada nem inserida crua.
- [ ] Ação sensível (aprovar, excluir, pagar) **não** é decidida só pelo conteúdo parseado — pede confirmação fora do canal.
- [ ] Rate limit + validação de identidade do remetente.

## Onde isto pode dar errado
Cobre o conhecido. Não substitui revisão humana em fluxo que toca dinheiro, dados pessoais ou permissões. Feature sensível → um humano olha o diff, sempre.
