# Decisões técnicas — Etapa 1: Coletor

## Proposta

O sistema de Recuperação da Informação terá como domínio **notícias recentes sobre futebol brasileiro**. A coleção produzida nesta primeira etapa será reutilizada nas etapas de representação/indexação e recuperação.

A intenção é permitir, nas próximas fases, consultas como:

- notícias sobre um clube;
- notícias sobre campeonato ou competição;
- mercado da bola e transferências;
- notícias da Seleção Brasileira;
- busca textual livre com ranking de relevância.

## Tipo de coletor

O projeto usa um **crawler focado, multissite, incremental e politeness-aware**.

- **Focado:** links e documentos recebem sinais temáticos; conteúdo sem relação com futebol brasileiro é descartado.
- **Multissite:** várias editorias esportivas são usadas como sementes.
- **Incremental:** o estado da fronteira e os documentos ficam em SQLite. Se o programa parar, ele continua de onde estava.
- **Polidez:** existe atraso mínimo entre requisições por domínio e respeito a `robots.txt`.

## Descoberta de URLs

A descoberta combina duas estratégias: navegação por links HTML a partir das páginas-semente e leitura de sitemaps declarados em `robots.txt`. Os sitemaps aumentam a cobertura e ajudam a atingir escala, mas as URLs ainda passam pelo filtro temático antes de entrar na fronteira.

## Fronteira

A fronteira é persistida em SQLite e possui:

- URL;
- profundidade;
- prioridade temática;
- URL de origem;
- status (`pending`, `processing`, `done`, `failed`).

Links com sinais como `futebol`, `brasileirao`, `copa-do-brasil`, nomes de clubes e competições recebem prioridade maior.

## Critério de parada

O critério principal é atingir o número-alvo de documentos válidos, configurado por padrão em **60.000 documentos**. O alvo foi definido acima dos 50 mil exigidos para a pontuação máxima do quesito de escala.

A coleta também termina caso a fronteira fique vazia. Se isso ocorrer antes do alvo, é possível adicionar novas sementes ou ampliar a janela temporal sem alterar a arquitetura.

## Recência

A configuração padrão considera os **últimos 365 dias**. Notícias cuja data de publicação seja anterior ao limite são ignoradas.

Por padrão, páginas sem data de publicação detectável também são descartadas (`allow_unknown_date: false`). Isso evita afirmar que uma página é recente quando essa informação não pôde ser comprovada.

## Políticas e tolerâncias

- respeito a `robots.txt`;
- atraso mínimo de 1 segundo por domínio;
- até 3 tentativas em falhas transitórias;
- backoff exponencial entre tentativas;
- timeout de 20 segundos;
- somente HTML;
- restrição aos domínios explicitamente permitidos;
- exclusão de imagens, vídeos, PDFs e outros arquivos não textuais;
- deduplicação por URL canônica e hash SHA-256 do texto;
- checkpoint automático em SQLite.

## Extração

Para cada notícia válida são armazenados:

- URL original;
- URL canônica;
- domínio;
- título;
- autor, quando disponível;
- descrição, quando disponível;
- data de publicação;
- data de coleta;
- texto principal da notícia;
- hash do conteúdo;
- status HTTP.

O texto principal é extraído com `trafilatura`, reduzindo menus, rodapés e outros elementos de navegação.

## Classificação temática

O filtro combina sinais do título, URL e texto. O documento precisa possuir sinais de **futebol** e também sinais de **contexto brasileiro**, como clubes brasileiros, Brasileirão, Copa do Brasil, CBF ou Seleção Brasileira.

Também há penalização de outras modalidades esportivas, como NBA, basquete, vôlei, tênis, F1, MMA e NFL.

## Escalabilidade

O crawler é assíncrono e possui concorrência global configurável, mantendo controle separado de intervalo por domínio. O armazenamento em SQLite reduz uso de memória e permite uma coleção grande sem manter todas as URLs em RAM.

Para a coleta final recomenda-se executar em uma máquina estável e acompanhar o crescimento com `scripts/stats.py`.
