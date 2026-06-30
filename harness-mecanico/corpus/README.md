# corpus/ — conhecimento mecânico consultável

> Componente de 1ª classe (não input solto): a base que o modelador, o dimensionamento analítico e os gates consultam. É daqui que sai a "regra herdada" que substitui calcular tudo do zero — material, peça-padrão, capacidade de fornecedor, regra de processo.

## O que construir

### `materiais/` — biblioteca de materiais
Uma entidade por material com as **propriedades que os solvers e o analítico exigem**: módulo de Young (E), Poisson (ν), densidade (ρ), limite de escoamento (σy) e ruptura (σu), limite de fadiga (Se), condutividade térmica, coef. de expansão, dureza. Mais disponibilidade/custo por fornecedor.
Começar pelos comuns: `aluminio-6061-t6`, `aco-1045`, `aco-inox-304`, `abs`, `pla`, `nylon-pa12` (SLS), `titanio-ti6al4v`.
> Cada propriedade com **fonte e unidade**. Propriedade sem fonte é palpite — proibido (Artigo 1).

### `fornecedores/` — perfis de capacidade (entidades versionadas, Artigo 5)
Uma entidade por (fornecedor × processo), **datada e versionada**. Default: JLC.
Campos: processo (CNC/3DP-FDM/3DP-SLA/3DP-SLS/chapa/injeção), materiais ofertados, **tolerância padrão** (ex.: ISO 2768-m, ±0.1 mm), feature mínima (parede, furo, raio interno, canto vivo), tamanho máximo, acabamentos, e o **modelo de custo** (para o orçamento). Data + versão obrigatórias.
> Alimenta o `dfm-linter` e o **rating de manufaturabilidade** (Artigo 6).

### `pecas-padrao/` — catálogo de prateleira
Parafusos (métrica, classes), porcas, arruelas, rolamentos, buchas, anéis, insertos. Com dimensões nominais, classe de ajuste (ISO 286) e furo/folga recomendados. Alimenta o BOM e o dimensionamento (ex.: diâmetro de parafuso → furo + torque de aperto).

### `processos/` — regras de manufatura por processo
DFM por processo, **genérico** (complementa o perfil específico do fornecedor): usinagem (acesso de ferramenta, raio mínimo de canto interno = raio da fresa, razão de profundidade), impressão (overhang crítico, espessura mínima de parede, orientação/suporte), fundição/injeção (ângulo de saída, parede uniforme, linha de partição), chapa (raio de dobra mínimo, relief).

### `normas/` — referência de normas (consulta, não cópia)
Ponteiros e regras extraídas das normas que os gates aplicam: ISO 2768 (tolerâncias gerais), ISO 286 (ajustes), ISO 1101 (GD&T), fatores de segurança típicos por aplicação. **Marcar proveniência** — evitar copiar texto de norma sob copyright; extrair a *regra*, citar a fonte.

## Princípio
O corpus é versionado em git (textual). Quando uma peça é validada, ela registra **contra qual versão** de material/fornecedor/norma — para que uma atualização do corpus não invalide peças antigas em silêncio.
