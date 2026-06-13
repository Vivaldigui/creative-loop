Você é um arquiteto de software sênior, engenheiro de IA, engenheiro de dados e especialista em integrações de marketing.

Sua tarefa é PROJETAR E IMPLEMENTAR, e não apenas explicar, uma plataforma chamada provisoriamente de “Creative Loop”, responsável por analisar anúncios históricos, gerar novos criativos com IA, cadastrar anúncios na Meta, coletar resultados e alimentar continuamente uma base de aprendizados.

Leia todas as instruções antes de iniciar.

1. OBJETIVO DO SISTEMA

Construir uma aplicação que execute o seguinte ciclo:

Conectar-se a uma conta de anúncios da Meta autorizada.

Buscar campanhas, conjuntos, anúncios, criativos e métricas históricas.

Relacionar cada criativo às suas métricas de desempenho.

Identificar anúncios vencedores e perdedores usando critérios configuráveis.

Baixar ou registrar as imagens pertencentes à própria conta de anúncios.

Usar Claude via API para analisar visualmente os criativos.

Extrair padrões abstratos, sem copiar peças de terceiros:

composição;

hierarquia visual;

enquadramento do produto;

paleta;

iluminação;

quantidade e posição de texto;

benefício principal;

chamada para ação;

estilo fotográfico;

elementos que chamam atenção;

possíveis causas de boa ou má performance.

Formular hipóteses de melhoria.

Gerar prompts estruturados e versionados.

Enviar os prompts e imagens de referência autorizadas à API de imagens da OpenAI.

Armazenar as imagens geradas.

Executar verificações automáticas de qualidade, marca e políticas.

Exibir os criativos em um painel para aprovação humana.

Após aprovação, criar campanha, conjunto, criativo e anúncio na Meta.

Criar o anúncio inicialmente como PAUSED.

Permitir sua ativação manual pelo painel.

Coletar métricas periodicamente.

Comparar as variações de forma estatisticamente responsável.

Registrar aprendizados.

Criar uma nova rodada de experimentos sem apagar o histórico anterior.

2. PRINCÍPIOS OBRIGATÓRIOS

Não use automação de navegador para abrir Claude, ChatGPT ou Meta Ads Manager.

Use apenas APIs oficiais.

Não publique ou ative anúncios automaticamente na primeira versão.

Todo anúncio criado na Meta deverá começar como PAUSED.

Nenhuma ação financeira poderá acontecer sem limites definidos.

Nunca aumente orçamento automaticamente sem aprovação humana.

Não copie anúncios de concorrentes.

Não trate duração de anúncio concorrente como prova de performance.

Não altere simultaneamente imagem, público, oferta, copy e landing page em um mesmo teste, salvo quando o usuário marcar o experimento como exploratório.

Não aprenda com anúncios sem volume mínimo de dados.

Não sobrescreva prompts anteriores. Versione tudo.

Não exponha chaves ou tokens em código, logs, frontend ou commits.

Não invente IDs, tokens, resultados, permissões ou métricas. Use placeholders claros quando uma informação precisar ser fornecida.

3. TECNOLOGIAS

Utilize:

Backend:

Python 3.12;

FastAPI;

SQLAlchemy 2;

Alembic;

Pydantic;

PostgreSQL;

pgvector, quando fizer sentido;

Redis;

Celery;

Celery Beat;

httpx;

SDK oficial da OpenAI;

SDK oficial da Anthropic ou chamadas HTTP oficiais;

integração com Meta Graph/Marketing API;

pytest.

Frontend:

Next.js;

TypeScript;

Tailwind CSS;

componentes acessíveis;

gráficos simples;

painel responsivo.

Infraestrutura:

Docker;

Docker Compose;

armazenamento local no desenvolvimento;

abstração compatível com S3 para produção;

GitHub Actions para testes e lint;

logs estruturados;

health checks.

Caso alguma biblioteca esteja obsoleta ou incompatível, utilize uma alternativa atual e documente a decisão.

4. ESTRUTURA DO REPOSITÓRIO

Crie uma estrutura semelhante a:

creative-loop/apps/api/web/worker/packages/meta_client/openai_image_client/anthropic_client/policy_engine/experiment_engine/analytics_engine/prompt_engine/migrations/tests/docs/scripts/storage/docker-compose.yml.env.exampleREADME.mdSECURITY.mdARCHITECTURE.mdIMPLEMENTATION_PLAN.md

Ajuste a estrutura quando houver justificativa técnica.

5. CONFIGURAÇÕES DE AMBIENTE

Crie .env.example com, no mínimo:

DATABASE_URL=REDIS_URL=SECRET_KEY=ENCRYPTION_KEY=

ANTHROPIC_API_KEY=ANTHROPIC_MODEL=

OPENAI_API_KEY=OPENAI_IMAGE_MODEL=gpt-image-2

META_APP_ID=META_APP_SECRET=META_ACCESS_TOKEN=META_GRAPH_API_VERSION=META_AD_ACCOUNT_ID=META_PAGE_ID=META_INSTAGRAM_ACTOR_ID=META_PIXEL_ID=

S3_ENDPOINT=S3_BUCKET=S3_ACCESS_KEY=S3_SECRET_KEY=

APP_BASE_URL=DEFAULT_CURRENCY=BRLDEFAULT_TIMEZONE=America/Sao_Paulo

DRY_RUN=trueREQUIRE_HUMAN_APPROVAL=trueMAX_DAILY_NEW_ADS=3MAX_DAILY_SPEND=MAX_EXPERIMENT_BUDGET=MAX_AUTOMATIC_BUDGET_INCREASE_PERCENT=0

Nunca coloque valores reais no repositório.

6. MODELO DE DADOS

Implemente as entidades:

UserOrganizationAdAccountProductBrandProfileBrandAssetAudienceProfileLandingPageSourceCampaignSourceAdSetSourceAdSourceCreativeCreativeAssetCreativeAnalysisPerformanceSnapshotPromptTemplatePromptVersionGeneratedCreativePolicyCheckQualityCheckExperimentExperimentVariantPublishedCampaignPublishedAdSetPublishedAdOptimizationDecisionLearningApprovalAuditLogIntegrationCredential

Todos os registros importantes devem possuir:

UUID;

organização;

data de criação;

data de atualização;

origem;

versão;

status;

metadados em JSON quando necessário.

Crie relacionamento rastreável:

anúncio de origem→ análise→ hipótese→ versão do prompt→ imagem gerada→ experimento→ anúncio publicado→ métricas→ decisão→ aprendizado.

7. IMPORTAÇÃO DA META

Implemente um cliente desacoplado para:

validar credenciais;

listar contas autorizadas;

importar campanhas;

importar conjuntos;

importar anúncios;

importar criativos;

importar imagens da própria conta;

coletar insights;

trabalhar com paginação;

tratar rate limits;

usar retries com exponential backoff;

registrar request IDs quando disponíveis;

impedir duplicação por IDs externos;

configurar campos e breakdowns;

preservar respostas brutas importantes para auditoria.

Métricas iniciais:

impressions;

reach;

frequency;

spend;

clicks;

link_clicks;

ctr;

cpc;

cpm;

landing_page_views;

adds_to_cart;

initiate_checkout;

purchases;

leads;

cost_per_result;

purchase_value;

ROAS.

Como alguns campos dependem do objetivo e da configuração da conta, normalize os resultados sem assumir que todos estarão disponíveis.

8. ANÁLISE VISUAL COM CLAUDE

Implemente um serviço que envie ao Claude:

imagem autorizada;

dados básicos do anúncio;

métricas;

segmento;

produto;

público;

posicionamento;

período;

copy;

título;

CTA;

landing page;

contexto da marca.

Exija saída estruturada em JSON validado por Pydantic.

Formato mínimo:

{"visual_summary": "","composition": {},"hierarchy": {},"product_presentation": {},"color_and_lighting": {},"text_analysis": {},"attention_elements": [],"strengths": [],"weaknesses": [],"performance_hypotheses": [],"elements_to_preserve": [],"elements_to_test": [],"policy_risks": [],"confidence": 0.0}

O modelo deve diferenciar:

observação visual;

informação proveniente de métricas;

hipótese;

conclusão ainda não comprovada.

9. PROMPT ENGINE

Crie um sistema de prompts estruturados.

Cada prompt deverá conter:

objetivo da peça;

formato;

dimensões;

produto;

referências autorizadas;

elementos obrigatórios;

identidade visual;

composição;

enquadramento;

fundo;

iluminação;

tipografia desejada;

texto exato;

margens;

CTA;

público;

posicionamento;

elementos proibidos;

alegações proibidas;

restrições da marca;

hipótese do experimento;

variável principal testada;

instruções de originalidade.

Armazene:

prompt completo;

prompt em campos estruturados;

versão;

autor;

modelo utilizado;

parâmetros;

criativo pai;

motivo da alteração;

aprendizado utilizado.

O agente nunca deve “melhorar o prompt” silenciosamente. Cada alteração cria uma nova versão e um diff legível.

10. GERAÇÃO DE IMAGENS

Implemente integração com a API oficial de imagens da OpenAI.

Funções:

gerar imagem do zero;

gerar várias variações;

editar imagem autorizada;

usar referências autorizadas;

escolher tamanho e qualidade;

salvar retorno com segurança;

calcular hash;

impedir arquivos duplicados;

registrar custo estimado quando disponível;

registrar modelo e parâmetros;

repetir chamadas apenas quando seguro;

tratar falhas e moderação.

Crie uma interface de provider para permitir outros geradores no futuro.

Para anúncios verticais, permita dimensões ou posterior redimensionamento para:

1080 × 1350;

1080 × 1920.

Para anúncios quadrados:

1080 × 1080.

Preserve o arquivo original gerado e crie derivados separadamente.

Não distorça imagens ao redimensionar.

11. QUALITY GATE

Antes da aprovação, execute verificações:

dimensões;

formato;

tamanho de arquivo;

presença do produto;

presença aproximada das cores da marca;

legibilidade;

texto cortado;

margens;

erros ortográficos;

conteúdo duplicado;

similaridade excessiva com outro criativo;

elemento obrigatório ausente;

possível uso indevido de logotipo;

possível alegação proibida;

informações contraditórias;

qualidade visual muito baixa.

Resultados:

PASSWARNINGBLOCKED

Itens BLOCKED não podem ser publicados.

Permita revisão humana e registre justificativa para qualquer override autorizado.

12. MOTOR DE POLÍTICAS

Crie regras configuráveis por segmento.

Inclua inicialmente verificações para:

promessas absolutas;

cura ou tratamento sem comprovação;

garantia de resultado;

antes e depois;

atributos pessoais sensíveis;

linguagem discriminatória;

sensacionalismo;

falsas urgências;

preço divergente;

texto não comprovado;

indução ao erro;

uso não autorizado de marcas;

alegações médicas;

alegações para produtos naturais e bem-estar.

Não declare que um anúncio está garantidamente aprovado pela Meta. Informe apenas que passou pela verificação interna.

13. APROVAÇÃO HUMANA

Crie uma fila de aprovação no frontend.

A tela deve exibir:

imagem;

prompt;

copy;

headline;

CTA;

hipótese;

variável do teste;

orçamento;

público;

posicionamentos;

verificações;

anúncios de origem;

aprendizados usados;

previsão de custo;

botão aprovar;

botão rejeitar;

campo de comentário;

botão solicitar nova variação.

Toda aprovação deve registrar usuário, data e conteúdo aprovado.

14. PUBLICAÇÃO NA META

Implemente fluxo para:

Validar configuração.

Fazer upload da imagem.

Criar ou reutilizar campanha.

Criar ou reutilizar conjunto.

Criar ad creative.

Criar anúncio.

Definir o anúncio como PAUSED.

Salvar IDs externos.

Consultar o status.

Registrar erros e rejeições.

Permitir ativação manual.

Permitir pausa de emergência.

Antes de qualquer chamada de escrita:

verificar DRY_RUN;

verificar aprovação;

verificar orçamento;

verificar limite diário;

verificar idempotency key;

registrar intenção no AuditLog.

No modo DRY_RUN, simule a operação e salve o payload, mas não realize chamadas de escrita.

15. MOTOR DE EXPERIMENTOS

Permita dois modos:

EXPLORATORY:

várias diferenças;

usado para descobrir direções criativas;

resultados não devem atribuir causalidade a um elemento isolado.

CONTROLLED:

apenas uma variável principal diferente;

orçamento e público comparáveis;

janela de análise consistente.

Variáveis possíveis:

composição;

cor de fundo;

posicionamento do produto;

presença de pessoa;

headline;

benefício;

demonstração;

prova;

CTA;

quantidade de texto.

Cada variante deve ter uma hipótese explícita.

Não declare vencedor antes de atingir critérios mínimos configuráveis.

Critérios possíveis:

gasto mínimo;

impressões mínimas;

cliques mínimos;

conversões mínimas;

número mínimo de dias;

diferença mínima;

confiança mínima.

Implemente inicialmente uma avaliação conservadora e documentada. Não prometa significância estatística quando não houver dados suficientes.

16. MOTOR DE APRENDIZADO

O sistema não deve fazer fine-tuning automático na primeira versão.

Implemente aprendizado por memória estruturada.

Cada Learning deverá registrar:

contexto;

segmento;

produto;

público;

posicionamento;

padrão observado;

evidências;

amostra;

confiança;

limitações;

métricas;

período;

experimento de origem;

status: provisional, confirmed ou rejected.

Um aprendizado provisional não pode ser tratado como regra definitiva.

Antes de criar novos prompts, consulte aprendizados relevantes por:

produto;

público;

formato;

objetivo;

similaridade semântica;

confiança;

recência.

Evite gerar infinitamente pequenas variações do mesmo anúncio.

Implemente penalidade por baixa diversidade criativa.

17. AUTOMAÇÕES

Crie tarefas para:

sincronização histórica;

sincronização incremental;

coleta periódica de métricas;

verificação de status;

atualização de anúncios em revisão;

cálculo de resultados;

detecção de gasto anormal;

alerta de anúncio rejeitado;

alerta de ausência de conversões;

relatório diário;

relatório semanal;

sugestão de nova rodada.

Na primeira versão, a sugestão de nova rodada deve exigir aprovação antes de gerar imagens.

18. SEGURANÇA

Implemente:

criptografia de credenciais;

segregação por organização;

RBAC;

logs sem segredos;

CSRF quando aplicável;

rate limiting;

validação de arquivos;

limite de upload;

proteção contra SSRF;

validação de URLs;

trilha de auditoria;

rotação de credenciais documentada;

princípio do menor privilégio.

Nunca envie tokens ao frontend.

Não armazene imagens ou informações de terceiros sem base autorizada.

19. PAINEL

Crie páginas para:

Dashboard;

Integrações;

Produtos;

Identidade da marca;

Biblioteca de anúncios;

Criativos vencedores;

Análises;

Prompts;

Imagens geradas;

Aprovações;

Experimentos;

Campanhas;

Métricas;

Aprendizados;

Políticas;

Auditoria;

Configurações.

O dashboard deve mostrar:

gasto;

conversões;

CPA;

ROAS;

CTR;

criativos ativos;

criativos em revisão;

criativos bloqueados;

experimentos em andamento;

melhores e piores variações;

alertas.

20. API INTERNA

Crie endpoints organizados, incluindo:

POST /integrations/meta/testPOST /integrations/openai/testPOST /integrations/anthropic/test

POST /sync/meta/historyPOST /sync/meta/incremental

GET /source-adsGET /source-ads/{id}POST /source-ads/{id}/analyze

POST /prompts/generatePOST /prompts/{id}/revise

POST /creatives/generateGET /creatives/{id}POST /creatives/{id}/quality-checkPOST /creatives/{id}/approvePOST /creatives/{id}/reject

POST /experimentsGET /experiments/{id}POST /experiments/{id}/evaluate

POST /publish/meta/dry-runPOST /publish/metaPOST /published-ads/{id}/activatePOST /published-ads/{id}/pause

GET /metricsGET /learningsGET /audit-logs

Implemente OpenAPI completo.

21. TESTES

Crie:

testes unitários;

testes de integração com mocks;

fixtures;

factories;

testes de idempotência;

testes de limites de orçamento;

testes de aprovação;

testes do DRY_RUN;

testes de versionamento de prompts;

testes do motor de políticas;

testes de segregação por organização;

testes de erros e retries;

teste do fluxo completo simulado.

Nenhum teste deve depender de gastar dinheiro ou publicar anúncio real.

22. DADOS DEMONSTRATIVOS

Crie seed de desenvolvimento contendo:

uma organização;

um produto fictício;

identidade de marca;

cinco anúncios históricos fictícios;

métricas variadas;

três análises;

três prompts;

quatro imagens placeholder;

um experimento;

um anúncio aguardando aprovação.

Marque claramente todos os dados como fictícios.

23. DOCUMENTAÇÃO

O README deve incluir:

objetivo;

arquitetura;

requisitos;

instalação;

execução;

migrações;

workers;

testes;

configuração das APIs;

modo DRY_RUN;

fluxo de aprovação;

publicação;

coleta de métricas;

solução de problemas;

limitações;

custos potenciais;

cuidados com políticas.

Crie também:

ARCHITECTURE.mdSECURITY.mdMETA_SETUP.mdOPENAI_SETUP.mdANTHROPIC_SETUP.mdEXPERIMENTATION.mdPOLICY_ENGINE.mdDEPLOYMENT.md

24. ETAPAS DE IMPLEMENTAÇÃO

Implemente nesta ordem:

Fase 1:

arquitetura;

Docker Compose;

backend;

banco;

autenticação;

frontend básico;

dados fictícios.

Fase 2:

importação somente leitura da Meta;

normalização das métricas;

biblioteca histórica.

Fase 3:

análise com Claude;

prompt engine;

versionamento.

Fase 4:

geração com OpenAI;

armazenamento;

quality gate;

aprovação.

Fase 5:

publicação Meta em DRY_RUN;

payloads;

idempotência;

auditoria.

Fase 6:

publicação real como PAUSED;

status e erros.

Fase 7:

experimentos;

avaliação;

aprendizados;

sugestões de nova rodada.

Conclua e teste cada fase antes de avançar.

25. CRITÉRIOS DE ACEITAÇÃO DO MVP

O MVP estará funcional quando for possível:

Subir todo o ambiente com Docker Compose.

Entrar no painel.

Cadastrar produto e identidade visual.

Testar as integrações.

Importar anúncios históricos ou usar mocks.

Visualizar métricas por criativo.

Selecionar um anúncio.

Gerar análise visual estruturada.

Gerar prompt versionado.

Gerar imagem pela OpenAI ou provider mock.

Executar quality e policy checks.

Aprovar a imagem.

Simular publicação.

Criar anúncio real como PAUSED quando DRY_RUN=false.

Coletar métricas.

Registrar um aprendizado.

Gerar uma nova hipótese com rastreabilidade completa.

26. FORMA DE TRABALHO

Primeiro:

Inspecione o diretório atual.

Crie IMPLEMENTATION_PLAN.md.

Registre premissas.

Liste riscos.

Crie a arquitetura.

Comece a implementação.

Não permaneça apenas no planejamento.

Execute comandos, crie arquivos, rode testes e corrija os problemas encontrados.

Quando uma informação externa for necessária, use um placeholder no formato:

PREENCHER_META_AD_ACCOUNT_IDPREENCHER_META_PAGE_IDPREENCHER_PIXEL_ID

Não invente valores.

Ao terminar cada fase:

rode lint;

rode testes;

atualize documentação;

apresente os arquivos alterados;

informe pendências reais;

faça commit local descritivo caso o repositório Git esteja configurado.

Priorize primeiro um MVP seguro, auditável e executável. Depois implemente recursos avançados.