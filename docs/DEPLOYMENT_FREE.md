# Hospedagem gratuita: guia para iniciantes

Este guia separa duas fases. Primeiro rode tudo localmente com provedores simulados e custo zero. Depois publique um prototipo usando os planos gratuitos.

## Arquitetura recomendada

| Parte | Servico | Plano inicial | Observacao |
|---|---|---|---|
| Frontend Next.js | Vercel Hobby | Gratuito | Somente prototipo pessoal/nao comercial |
| API FastAPI | Render Web Service | Gratuito | Desliga apos 15 minutos sem acesso e demora para acordar |
| PostgreSQL | Neon Free | Gratuito | 0,5 GB por projeto no plano gratuito |
| Imagens | Cloudflare R2 | Franquia gratuita | Exige ativar faturamento; configure limite/alerta |
| Redis/Celery | Nao usar no primeiro deploy | Zero | Relatorios agendados e sincronizacoes automaticas ficam desligados |
| Monitoramento | Logs do Render; Sentry depois | Gratuito | Sentry Developer pode ser adicionado quando o app estiver estavel |

Fontes oficiais consultadas em 11 de junho de 2026:

- Render Free: https://render.com/docs/free
- Neon Free: https://neon.com/docs/introduction/plans
- Vercel Hobby: https://vercel.com/docs/plans/hobby
- Cloudflare R2: https://developers.cloudflare.com/r2/pricing/
- Upstash Redis: https://upstash.com/pricing/redis
- Sentry: https://docs.sentry.io/pricing/

Planos gratuitos servem para aprendizado e prototipos. Eles nao oferecem a disponibilidade de uma producao paga. O Vercel Hobby tambem limita o uso a projetos pessoais e nao comerciais.

## Fase 1: usar localmente sem pagar

O arquivo `.env` ja deve manter estas travas:

```env
ANTHROPIC_PROVIDER=mock
IMAGE_PROVIDER=mock
META_PROVIDER=mock
DRY_RUN=true
META_WRITE_ENABLED=false
REQUIRE_HUMAN_APPROVAL=true
```

No PowerShell, a partir da raiz do projeto:

```powershell
.\scripts\run-local.ps1 -NoWorker
```

Abra `http://localhost:3000` e entre com `admin@demo.example` / `demo1234`.
Esses dados sao ficticios e devem ser usados somente no computador local.

## Fase 2: preparar o codigo no GitHub

Render e Vercel implantam o projeto a partir de um repositorio Git. Crie um repositorio privado no GitHub e envie esta pasta. Confirme antes que `.env` nao aparece nos arquivos enviados.

Nunca copie o conteudo do `.env` para GitHub, chat, captura de tela ou documentacao.

## Fase 3: criar o PostgreSQL no Neon

1. Crie uma conta em https://console.neon.tech.
2. Crie um projeto, por exemplo `creative-loop`.
3. Copie a connection string do banco.
4. Troque somente o inicio `postgresql://` por `postgresql+asyncpg://`.

Exemplo de formato:

```text
postgresql+asyncpg://USUARIO:SENHA@HOST/neondb?ssl=require
```

Guarde esse valor para a variavel `DATABASE_URL` do Render. Nao o coloque no repositorio.

## Fase 4: criar o bucket no Cloudflare R2

1. Entre em https://dash.cloudflare.com e abra `Storage & databases > R2`.
2. Ative o R2 e crie um bucket chamado `creative-loop`.
3. Crie um token com permissao de leitura e escrita apenas nesse bucket.
4. Guarde os quatro valores abaixo.

```text
S3_ENDPOINT=https://SEU_ACCOUNT_ID.r2.cloudflarestorage.com
S3_BUCKET=creative-loop
S3_ACCESS_KEY=Access Key ID
S3_SECRET_KEY=Secret Access Key
```

Use `S3_REGION=auto`. O codigo usa URLs assinadas, portanto o bucket pode continuar privado.

## Fase 5: gerar chaves exclusivas de producao

Nao reutilize as chaves do `.env` local. Rode:

```powershell
python scripts/gen_keys.py
```

Guarde `SECRET_KEY` e `ENCRYPTION_KEY`. O comando nao altera arquivos.

## Fase 6: publicar a API no Render

1. Acesse https://dashboard.render.com.
2. Escolha `New > Blueprint` e conecte o repositorio.
3. O Render detectara o arquivo `render.yaml`.
4. Preencha os valores secretos solicitados:

```text
DATABASE_URL
SECRET_KEY
ENCRYPTION_KEY
S3_ENDPOINT
S3_BUCKET
S3_ACCESS_KEY
S3_SECRET_KEY
```

O container executa as migracoes automaticamente antes de iniciar a API. Ao finalizar, teste `https://SEU-SERVICO.onrender.com/readyz`.

A resposta deve conter `"status":"ok"` e `"db":true`.

## Fase 7: criar seu primeiro administrador

No seu computador, use temporariamente a URL do Neon no PowerShell:

```powershell
$env:DATABASE_DRIVER = "postgres"
$env:DATABASE_URL = "postgresql+asyncpg://USUARIO:SENHA@HOST/neondb?ssl=require"

.\apps\api\.venv\Scripts\python.exe scripts\create_admin.py `
  --email "seu-email@exemplo.com" `
  --name "Seu Nome" `
  --organization "Sua Empresa" `
  --slug "sua-empresa"

Remove-Item Env:DATABASE_DRIVER
Remove-Item Env:DATABASE_URL
```

A senha nao aparece na tela e deve ter pelo menos 12 caracteres.

## Fase 8: publicar o frontend na Vercel

1. Acesse https://vercel.com/new e importe o mesmo repositorio.
2. Em `Root Directory`, escolha `apps/web`.
3. Adicione estas variaveis de ambiente:

```text
NEXT_PUBLIC_API_URL=/api
API_PROXY_TARGET=https://SEU-SERVICO.onrender.com
```

4. Clique em Deploy.
5. No Render, troque `CORS_ORIGINS` pela URL final da Vercel, sem barra no final.
6. Abra a URL da Vercel e entre com o administrador criado na fase anterior.

O caminho `/api` e encaminhado pela Vercel para o Render. Isso mantem o cookie de login na mesma origem e evita bloqueios de cookies entre sites.

## APIs reais: ordem segura

Nao e necessario configurar Anthropic, OpenAI ou Meta para validar o produto. Os mocks ja permitem percorrer a interface.

Quando o prototipo estiver funcionando, habilite uma integracao por vez:

1. Meta somente leitura: preencha as credenciais e use `META_PROVIDER=real`, mantendo `DRY_RUN=true` e `META_WRITE_ENABLED=false`.
2. Anthropic: preencha `ANTHROPIC_API_KEY` e mude `ANTHROPIC_PROVIDER=real`.
3. OpenAI: preencha `OPENAI_API_KEY` e mude `IMAGE_PROVIDER=openai`.
4. Meta escrita: somente depois de teste em conta sandbox, revisao de orcamento e aprovacao humana.

Anthropic e OpenAI normalmente exigem faturamento e cobram por uso. Meta nao cobra pela chamada da API, mas anuncios publicados podem consumir o saldo da conta de anuncios.

## O que ainda nao deve ser ligado

- Redis e Celery: o Render nao oferece worker gratuito. Adicione Upstash e um worker pago somente quando precisar de tarefas agendadas.
- `DRY_RUN=false`: mantenha `true` durante toda a implantacao inicial.
- `META_WRITE_ENABLED=true`: mantenha `false` ate concluir o teste sandbox e o sign-off.
- Banco SQLite no Render: o disco gratuito e efemero e os dados seriam perdidos.
- Armazenamento local no Render: arquivos seriam perdidos ao reiniciar ou ao servico dormir.

## Observacao sobre limite de gastos

O codigo atual usa `MAX_DAILY_SPEND` como limite global da instalacao, em BRL. Ele ainda nao possui um limite separado por organizacao. O Blueprint inicia com `MAX_DAILY_SPEND=10.0`, alem de manter publicacao real bloqueada. Antes de atender varias organizacoes ou liberar escrita na Meta, implemente e revise o limite por organizacao.
