# Fase 6 — Plano de Publicação Real na Meta (PAUSED) + Status, Erros e Ativação Manual

> **Status:** PLANEJAMENTO. Nenhum código deve ser implementado a partir deste documento sem aprovação.
> **Princípio mestre:** a Fase 6 reaproveita 100% da infraestrutura de guards, idempotência,
> AuditLog, payloads DTO e serialização já construída na Fase 5. A escrita real é um *novo caminho de saída*
> acoplado por trás do mesmo conjunto de validações — nunca um bypass.

---

## 0. Mapa do que já existe (Fase 5) e o que muda

| Componente Fase 5 (pronto) | Papel | Mudança na Fase 6 |
|---|---|---|
| `packages/meta_client/publish/dtos.py` | DTOs Pydantic, status sempre PAUSED (frozen) | **Reutilizar sem alterar.** A garantia `_force_paused` é a espinha dorsal do requisito "PAUSED obrigatório". |
| `packages/meta_client/publish/serialization.py` | DTO → dict Graph API | Reutilizar; o `RealPublisher` envia esses mesmos dicts. |
| `publish/dry_run_publisher.py` | Publisher simulado | Permanece. Continua sendo o publisher quando `DRY_RUN=true`. |
| `publish/write_client_real.py` (`RealMetaWriteClient`) | Stub que levanta `MetaPublishDisabledError` | **Implementar de verdade** (transport de escrita). |
| `publish/factory.py` (`get_meta_publisher`) | `assert dry_run` | **Reescrever** para selecionar Dry/Real via gate completo. |
| `meta_client/transport.py` (`MetaGraphTransport`) | GET-only, retries/backoff/rate-limit/request-id | **Não tocar** (mantém read-only). Criar transport de escrita separado (ver §3). |
| `services/publication_guards.py` | 13 guards puros | **Estender** com guards específicos de escrita real (ver §1). |
| `services/publication_service.py` | Orquestra DRY_RUN | **Estender** com método `publish_real()` + workflow por etapas. |
| `models/publication.py`, `models/publish.py`, `models/audit.py` | Persistência | **Estender** (novos campos/estados, sem quebrar Fase 5). |
| `routers/publish.py` (`POST /publish/meta` → 501) | Endpoint desabilitado | **Implementar** + novos endpoints de status/ativação/pausa. |
| `apps/web/app/publish/page.tsx` | UI DRY_RUN | **Estender** com confirmação, progresso por etapa, ativar/pausar. |

**Conclusão de arquitetura:** a Fase 6 é majoritariamente *aditiva*. O risco está concentrado no novo
transport de escrita, no workflow recuperável e no gate. Tudo o mais é extensão de contratos já estáveis.

---

## 1. O Gate de Publicação Real (as 11 condições)

A escrita real **só** pode ocorrer quando **todas** forem verdadeiras. Ausência de qualquer uma = bloqueio duro.
Implementado como uma sequência de guards (mesmo padrão `CheckResult` da Fase 5), executados **antes** de
qualquer chamada de rede e **re-executados** em pontos críticos (ativação).

| # | Condição | Onde verificar | Guard novo/existente |
|---|---|---|---|
| 1 | `DRY_RUN=false` | `Settings.dry_run` | **novo** `guard_real_mode_enabled` (inverso do `guard_dry_run_enabled`) |
| 2 | `META_WRITE_ENABLED=true` | nova flag (ver §2) | **novo** `guard_write_enabled` |
| 3 | Credenciais válidas | health check de token (ver §8) | **novo** `guard_credentials_valid` (usa cache/health, não expõe token) |
| 4 | Usuário autorizado | `actor.role` | estender `guard_rbac` → exigir `owner`/`admin` para criar; `owner` para ativar |
| 5 | Aprovação humana válida | `Approval.decision == approved` + snapshot íntegro | estender `guard_approval_present` (validar que o approval cobre o payload atual) |
| 6 | Criativo não BLOCKED | quality/policy checks | reutilizar `guard_not_blocked` |
| 7 | Orçamento dentro dos limites | `MAX_DAILY_SPEND`, `MAX_EXPERIMENT_BUDGET`, `MAX_DAILY_NEW_ADS` | reutilizar `guard_daily_spend_limit`, `guard_experiment_budget`, `guard_daily_ads_count` |
| 8 | Idempotency key válida | `PublicationAttempt` unique (org, key) | reutilizar `guard_idempotency` (+ semântica de retry, ver §4) |
| 9 | Configuração completa | sem placeholders `PENDING_*`/`PREENCHER_*` em ad_account/page/(ig)/(pixel) | **promover** `guard_min_config` de *warning* → *blocked* quando `dry_run=false` |
| 10 | AuditLog ativo | sanity check de que o subsistema de auditoria está gravável | **novo** `guard_audit_available` (defensivo; falha fechado) |
| 11 | Status inicial PAUSED | garantido nos DTOs (`status` frozen + `_force_paused`) | reforço por **teste** + assert no `RealPublisher` antes de cada POST |

### Pontos de projeto do gate
- **Falha fechada:** qualquer erro inesperado ao montar o contexto do gate ⇒ tratar como bloqueio.
- **Ordem:** flags/credenciais/RBAC primeiro (barato e mais sensível), depois budget/config.
- **Reuso máximo:** `run_all_guards` ganha um parâmetro `mode="real"` que ativa os guards extras e
  endurece `guard_min_config`. Os guards da Fase 5 não mudam de comportamento no modo DRY_RUN.
- **Registro:** o resultado completo de todos os guards é persistido em `PublicationAttempt.checks`
  e resumido em `AuditLog.limits_checked` — exatamente como na Fase 5.

---

## 2. Configuração / Variáveis de ambiente (novas)

Adicionar a `Settings` (`apps/api/app/config.py`) e a `.env.example`:

```
META_WRITE_ENABLED=false            # interruptor mestre independente de DRY_RUN
META_REQUIRE_ELEVATED_FOR_ACTIVATION=true
META_WRITE_MAX_RETRIES=3            # retries para operações seguras (idempotentes)
META_WRITE_TIMEOUT_S=60
META_ACTIVATION_REQUIRE_CONFIRMATION=true
META_LIVE_TEST_ENABLED=false        # habilita procedimento de teste ao vivo (§13)
CREDENTIAL_ROTATION_WARN_DAYS=30    # alerta de expiração de token
```

**Matriz de modos resultante:**

| `DRY_RUN` | `META_WRITE_ENABLED` | `META_PROVIDER` | Comportamento |
|---|---|---|---|
| `true` | qualquer | qualquer | DRY_RUN (Fase 5). Nenhuma escrita. **Default seguro.** |
| `false` | `false` | qualquer | Bloqueado por guard #2. Nenhuma escrita. |
| `false` | `true` | `mock` | Escrita **simulada via mock client** (testes de integração ponta-a-ponta sem rede). |
| `false` | `true` | `real` | **Escrita real**. Exige todo o gate (§1) verde. |

> Dois interruptores (`DRY_RUN` **e** `META_WRITE_ENABLED`) são exigidos de propósito: defesa em
> profundidade. Mudar um único env var nunca deve, sozinho, habilitar gasto real.

---

## 3. MetaWriteClient — design

### 3.1 Transport de escrita (novo: `WriteGraphTransport`)
Separado do `MetaGraphTransport` (read-only) para preservar a garantia "Fase 2 nunca escreve".
Compartilha as utilidades (appsecret_proof, redação de segredos, parsing de erro, inspeção de
`x-business-use-case-usage`, captura de `x-fb-request-id`), idealmente extraídas para um módulo comum
`transport_base.py` para evitar duplicação.

Responsabilidades:
- `POST` autenticado com `appsecret_proof`.
- Upload multipart para `/{account}/adimages`.
- Classificação de erro Graph API (reaproveitar `_AUTH_ERROR_CODES`, `_RATE_LIMIT_CODES`, `_RETRIABLE_HTTP`).
- Captura **obrigatória** de `x-fb-request-id` em **toda** resposta (sucesso e erro) → persistida por etapa.
- Backoff exponencial com jitter (já existe a fórmula `_backoff`).
- Respeito a rate-limit headers (já existe `_inspect_usage` / `_rate_wait`).
- Nunca logar `access_token`/`appsecret_proof`/multipart bytes.

### 3.2 `RealMetaWriteClient` (implementar o stub)
Mapeia 1:1 os métodos já declarados no stub, agora chamando o `WriteGraphTransport`:

| Método | Endpoint Graph | Retry permitido? | Justificativa |
|---|---|---|---|
| `validate_token()` (novo) | `GET /me`, `GET /{account}` | **Sim** | leitura idempotente |
| `upload_image(account, bytes, filename)` | `POST /{account}/adimages` | **Sim, com cuidado** | Meta deduplica por hash de imagem; reupload do mesmo arquivo retorna o mesmo `image_hash`. Idempotente na prática. |
| `create_campaign(account, payload)` | `POST /{account}/campaigns` | **Não** auto-retry cego | criação não-idempotente; ver §4 (reconciliação por `name`/tag antes de recriar) |
| `create_adset(account, payload)` | `POST /{account}/adsets` | **Não** | idem |
| `create_ad_creative(account, payload)` | `POST /{account}/adcreatives` | **Não** | idem |
| `create_ad(account, payload)` | `POST /{account}/ads` (status=PAUSED) | **Não** | idem |
| `get_status(node_id)` (novo) | `GET /{id}?fields=effective_status,configured_status,...` | **Sim** | leitura |
| `update_ad_status(ad_id, status)` | `POST /{ad_id}` (`status=ACTIVE|PAUSED`) | **Sim** para PAUSE; **Não** auto para ACTIVATE | pausar é seguro/idempotente; ativar é ação deliberada |
| `update_budget(...)` | `POST /{adset_id}` | fora do escopo da Fase 6 (Fase 7) | — |

### 3.3 Política de retry — resumo normativo
- **Pode receber retry automático (seguro/idempotente):** validação de token, GETs de status,
  `upload_image` (dedup por hash), `update_ad_status → PAUSED`, e erros **claramente transitórios**
  (HTTP 5xx, timeout de conexão **antes** de a Meta confirmar criação, rate-limit).
- **NÃO pode receber retry automático:** qualquer `create_*` (campaign/adset/creative/ad) e
  `update_ad_status → ACTIVE`. Em vez de retry cego, entra a **reconciliação** (§4): consultar se o
  recurso já foi criado (por `name` + tag de idempotência em metadados) antes de tentar novamente.
- **Timeout/erro de rede após POST de criação** = caso ambíguo (recurso pode ter sido criado). Nunca
  retry cego → marcar etapa `requires_manual_review` e disparar reconciliação.

### 3.4 Erros da Graph API
Mapear para exceções tipadas (estender as já existentes em `transport.py`):
- `MetaAuthError` (190/102/10/200/803) → não-retryable, marca credencial como inválida, alerta.
- `MetaRateLimitError` (4/17/32/613/80000/80004 / HTTP 429) → backoff, retry dentro do limite.
- `MetaPermissionError` (novo) → escopo ausente; bloqueia e instrui o usuário.
- `MetaPolicyRejectionError` (novo) → rejeição de política/conteúdo (códigos 1487xxx etc.) → não-retryable;
  etapa `failed` com motivo; **proíbe ativação**.
- `MetaTransientError` (5xx/timeout) → retryable conforme política.
- Toda exceção carrega `request_id`, `error_code`, `error_subcode`, `fbtrace_id`, mensagem sanitizada.

---

## 4. Idempotência, falhas parciais e reconciliação

### 4.1 Identidade de idempotência
- Chave externa: `idempotency_key` (cliente) + `payload_hash` canônico (já calculado na Fase 5).
- **Tag de correlação injetada nos recursos Meta:** ao criar campaign/adset/ad, incluir a
  `idempotency_key`/`attempt_id` no campo `name` (sufixo) e/ou em `url_tags`/metadados. Isso permite a
  reconciliação encontrar recursos órfãos criados por uma tentativa anterior que falhou após a criação.
- Constraint `uq_attempt_org_idem_key` (já existe) garante uma tentativa por chave.

### 4.2 Cenários de falha parcial e resolução (sem duplicar recursos)

| Cenário | Estado salvo | Reconciliação na re-tentativa |
|---|---|---|
| Imagem criada, campanha falhou | `image_uploaded` + `image_hash` salvo | reusa `image_hash` (dedup Meta), retoma de `campaign_resolved` |
| Campanha criada, conjunto falhou | `campaign_resolved` + `meta_campaign_id` salvo | reusa campaign_id, retoma de `adset_resolved` |
| Creative criado, anúncio falhou | `creative_created` + `meta_creative_id` salvo | reusa creative_id, cria apenas o ad |
| Timeout **após** Meta criar o recurso | etapa fica `requires_manual_review` | **GET por tag/name** para descobrir o id real antes de qualquer novo POST |
| Resposta sem `id` | etapa `failed` (resposta inválida) | reconciliar via GET por tag; nunca assumir sucesso |
| Token expirado no meio | etapa atual `failed` (auth) | renovar credencial → retomar da última etapa concluída |
| Limite atingido (rate) | etapa pausa, backoff | retoma automaticamente dentro do retry seguro |
| Permissão ausente | etapa `failed` (permission) | bloqueia; nada a reconciliar |
| Rejeição de política | etapa `failed` (rejection) | bloqueia; recurso pode existir PAUSED mas **não ativável** |

### 4.3 Princípio de reconciliação
> **Antes de criar qualquer recurso, verificar se a etapa anterior já tem um id persistido; se a etapa
> falhou de forma ambígua, fazer GET por tag de idempotência antes de recriar.** Criação só ocorre quando
> a reconciliação confirma que o recurso não existe. Resultado: re-execução de uma tentativa nunca
> duplica campanha/conjunto/creative/anúncio.

### 4.4 Compensação
A Fase 6 **não deleta** recursos automaticamente (risco de apagar algo legítimo — viola princípio
"não sobrescreva sem ver"). Em vez disso:
- recursos órfãos/parciais ficam **PAUSED** (nunca gastam) e são listados como `requires_manual_review`;
- o painel mostra o recurso parcial e oferece *retomar* (reconciliar) ou *marcar como abandonado*;
- deleção real só por ação manual explícita do usuário, registrada em AuditLog.

---

## 5. Workflow persistido por etapas (state machine recuperável)

Novo modelo **`PublicationStep`** (ou campo `workflow_state` + tabela de eventos) ligado a `PublicationAttempt`.
Estados (exatamente os pedidos):

```
validated
  → image_uploaded
  → campaign_resolved
  → adset_resolved
  → creative_created
  → ad_created_paused
  → status_checked
  → completed
(ramos)  → failed
         → requires_manual_review
```

### Projeto
- Cada transição grava: estado, timestamp, `request_id` Meta, id externo resultante, erro (se houver).
- **Recuperável:** ao re-invocar uma tentativa, o serviço lê o último estado e retoma a partir dele
  (não do zero), aplicando reconciliação (§4).
- Idealmente executado por uma **task Celery** (`publish_real_task`) para sobreviver a timeouts HTTP,
  com o endpoint retornando 202 + `attempt_id` e o frontend fazendo polling de status (§10/§11).
  O estado vive no banco, não na task → restart do worker não perde progresso.
- `completed` exige `ad_created_paused` **e** `status_checked` confirmando `effective_status` esperado
  (ex.: `PAUSED`/`PENDING_REVIEW`).
- Invariante: nenhuma etapa transiciona para `completed` com o ad em estado ativo.

---

## 6. Ativação manual (endpoint separado, jamais automática)

A criação termina **sempre** em PAUSED. Ativar é um fluxo distinto, deliberado.

`POST /published-ads/{id}/activate` deve:
1. Exigir **permissão elevada** (`owner`; configurável via `META_REQUIRE_ELEVATED_FOR_ACTIVATION`).
2. Exigir **confirmação explícita** (corpo com `confirm: true` + nome/typed-confirmation do recurso).
3. **Re-verificar limites** de orçamento no momento da ativação (não confiar na verificação da criação).
4. Verificar que o ad **não está rejeitado** (consultar `effective_status`; se `DISAPPROVED`/rejeição → 409, proíbe).
5. Verificar gate mínimo (DRY_RUN=false, WRITE_ENABLED, credenciais válidas).
6. Registrar AuditLog **antes** (intenção) e **depois** (resultado), com `actor_id` e timestamp.
7. Chamar `update_ad_status(ad_id, "ACTIVE")` (sem auto-retry; ver §3.3).
8. Persistir novo `effective_status` e gravar evento.

**Nunca** existe caminho de ativação automática — não há job/celery que ative; só o endpoint manual.
Teste dedicado garante que nenhuma rota/worker chama `update_ad_status("ACTIVE")` fora deste endpoint.

### Pausa e pausa de emergência
- `POST /published-ads/{id}/pause` — pausa normal (`owner`/`admin`), AuditLog, idempotente.
- `POST /published-ads/{id}/emergency-pause` — pausa imediata, **caminho mais permissivo de papel**
  (qualquer membro autenticado da org pode parar gasto), **mínimas pré-condições** (só precisa de
  credencial válida + id), prioridade sobre rate-limit interno, AuditLog com flag `emergency=true`.
  Filosofia: parar gasto deve ser sempre mais fácil que iniciá-lo.

---

## 7. Credenciais

- **Criptografia:** já existe `IntegrationCredential.encrypted_data` via Fernet (`security/fernet.py`).
  Fase 6 passa a ler o token de escrita de `IntegrationCredential` (por org) em vez de só do `.env`,
  mantendo `.env` como fallback de desenvolvimento.
- **Armazenamento:** apenas no backend, criptografado em repouso. Nunca em `PublishedAd.payload`,
  nunca em `AuditLog` (sanitização já existe em `_sanitize_payload`), nunca no frontend.
- **Escopos mínimos:** documentar e validar `ads_management` (escrita) + `ads_read`. O health check
  deve reportar escopos presentes/faltantes sem exibir o token.
- **Rotação/expiração:** campo `last_verified_at` + `expires_at` (novo) em `IntegrationCredential`;
  job/alerta quando faltar `CREDENTIAL_ROTATION_WARN_DAYS` para expirar; procedimento de rotação
  documentado em `docs/META_SETUP.md`.
- **Health check seguro / teste sem exibir:** `POST /integrations/meta/test` estendido para validar
  token de escrita via `GET /me` + checagem de escopos, retornando apenas booleanos/escopos —
  **nunca** o token. Logs sanitizados (redação já implementada no transport).
- **Princípio do menor privilégio:** leitura usa token read; escrita usa credencial dedicada quando
  possível.

---

## 8. Modelo de dados (extensões; sem quebrar Fase 5)

Nova migração Alembic. Mudanças aditivas:

- **`PublishedAd`** (já tem `meta_*_id`, `status`, `error_detail`):
  - `effective_status: str | None` (status reportado pela Meta).
  - `last_status_checked_at`, `activated_at`, `activated_by`, `paused_at`, `paused_by`.
  - `rejection_reason: str | None`.
  - `workflow_state: str` (espelho do último estado da máquina de §5).
- **`PublicationAttempt`** (imutável por tentativa):
  - `mode` passa a aceitar `REAL` além de `DRY_RUN`.
  - `result` aceita `published | partial | requires_manual_review | failed` (além de `simulated|rejected`).
  - `meta_request_ids: JSON` (lista de `x-fb-request-id` por etapa).
- **Novo `PublicationStep`**: `attempt_id`, `state`, `started_at`, `finished_at`, `meta_node_id`,
  `meta_request_id`, `error_code`, `error_detail` (sanitizado), `is_recoverable`.
- **`IntegrationCredential`**: `expires_at`, `scopes: JSON`, `last_health_status`.
- **`AuditLog`**: novas `action`s (`publish_real_intent/result`, `activate_intent/result`,
  `pause`, `emergency_pause`) e flag `emergency: bool`. Estrutura atual já suporta a maioria.

Invariante de banco: `status="active"` em `PublishedAd` só pode existir se houver um AuditLog de
`activate_result=success` correspondente (validável por teste de consistência).

---

## 9. Endpoints

| Método | Rota | Papel | Função |
|---|---|---|---|
| `POST` | `/publish/meta` | owner/admin | Inicia publicação **real** (gate completo §1). Retorna 202 + `attempt_id` (assíncrono via Celery) ou 201 (síncrono). Cria sempre PAUSED. |
| `GET` | `/publication-attempts/{id}/status` | membro | Estado do workflow por etapa (§5), erros, request_ids. |
| `POST` | `/published-ads/{id}/refresh-status` | membro | Consulta a Meta (`effective_status`) e atualiza. |
| `POST` | `/published-ads/{id}/activate` | owner (elevado) | Ativação manual (§6): confirmação + re-checagem de limites + proíbe rejeitado. |
| `POST` | `/published-ads/{id}/pause` | owner/admin | Pausa normal. |
| `POST` | `/published-ads/{id}/emergency-pause` | qualquer membro | Pausa de emergência (mínimas pré-condições). |

Notas:
- `POST /publish/meta` deixa de retornar 501; passa a aplicar o gate. Se `DRY_RUN=true` ou
  `META_WRITE_ENABLED=false`, retorna **erro de gate explicando qual condição falhou** (não 501).
- Reaproveitar `_correlation_id`, RBAC `require_roles`, segregação por org (`get_current_org`) já existentes.
- OpenAPI completo (FastAPI gera automaticamente).

---

## 10. Frontend

Estender `apps/web/app/publish/page.tsx` e criar uma página/aba de **anúncios publicados**:

- **Tela de confirmação de publicação real** (modal distinto do DRY_RUN): banner vermelho "ESCRITA REAL",
  resumo de riscos, orçamento diário, limites configurados, conta/campanha/conjunto alvo, e o aviso
  "criado como PAUSED — não gasta até ativação manual". Exigir confirmação digitada.
- **Progresso por etapa:** stepper visual espelhando a máquina de §5 (validated → … → completed),
  com request_id e id externo por etapa, atualizando via polling de `/publication-attempts/{id}/status`.
- **Erros e rejeições:** exibir `error_code`/motivo sanitizado por etapa; destacar rejeição de política.
- **Botões de ação:** Ativar (desabilitado se rejeitado / sem permissão elevada; exige confirmação),
  Pausar, e **Pausa de Emergência** (botão vermelho sempre acessível).
- **Histórico auditável:** lista de AuditLogs (intenção/resultado, ator, horário) por anúncio.
- Reutilizar `DryRunBanner`/`CheckRow`/`JsonViewer` já prontos.

---

## 11. Testes (cliente Meta mockado; nenhum custo real)

Unitários + integração, todos com `META_PROVIDER=mock` ou `RealMetaWriteClient` mockado via httpx
transport stub. **Nenhum teste gasta dinheiro ou publica de verdade.**

Cobertura obrigatória:
- credencial inválida / token expirado / permissão ausente → bloqueio correto, sem escrita.
- `DRY_RUN=true` ⇒ caminho real **inalcançável** (guard #1).
- `META_WRITE_ENABLED=false` ⇒ bloqueio (guard #2).
- criativo não aprovado / BLOCKED ⇒ bloqueio.
- limite de orçamento/diário/experimento excedido ⇒ bloqueio.
- idempotência: mesma chave + mesmo payload = retry seguro (sem 2º recurso); chave + payload diferente = conflito.
- timeout após criação ⇒ `requires_manual_review`, sem duplicação na re-tentativa.
- retry: 5xx/rate-limit retorna e conclui; `create_*` **não** sofre retry cego.
- falha parcial (cada um dos 5 pontos de quebra) + reconciliação reusando ids salvos.
- **status inicial PAUSED obrigatório:** assert em todos os DTOs e na chamada do publisher real.
- ativação manual: exige papel elevado + confirmação + re-checagem de limites; rejeitado ⇒ proibido.
- pausa e pausa de emergência funcionam e auditam.
- AuditLog gravado em intenção e resultado; sanitização (sem tokens) — estender `test_audit_no_secrets`.
- segregação por organização nos novos endpoints (estender `test_org_isolation`).
- **nenhuma ativação automática:** teste que varre rotas/tasks e garante que `ACTIVE` só é setado pelo
  endpoint de ativação manual.

Arquivos sugeridos: `tests/unit/test_real_write_client.py`, `tests/unit/test_publish_gate.py`,
`tests/unit/test_reconciliation.py`, `tests/integration/test_publish_real_flow.py`,
`tests/integration/test_activation_flow.py`, `tests/integration/test_emergency_pause.py`.

---

## 12. Testes reais com segurança (opcional, ambiente autorizado)

Procedimento **manual e opt-in**, jamais parte da suíte automatizada:
- só roda com `META_LIVE_TEST_ENABLED=true` + conta de teste/sandbox autorizada explicitamente;
- **não usar orçamento real sem autorização** documentada;
- criar somente recurso **PAUSED**; **nunca ativar automaticamente**;
- procedimento manual documentado em `docs/META_SETUP.md` (passo a passo + checklist de limpeza);
- a suíte automatizada **pula** o teste ao vivo por padrão (`pytest.mark.skipif`);
- teste ao vivo nunca é requisito de CI/aceitação.

---

## 13. Premissas, riscos e ordem de implementação

### Premissas
- IDs reais (`META_AD_ACCOUNT_ID`, `META_PAGE_ID`, etc.) serão fornecidos pelo usuário; placeholders
  `PENDING_*`/`PREENCHER_*` continuam bloqueando escrita real (guard #9 endurecido).
- Token de escrita possui escopo `ads_management`; caso contrário, guard de permissão bloqueia.
- Versão Graph API `v21.0` (config). Campos de status: `configured_status`/`effective_status`.

### Riscos
- **Ambiguidade pós-timeout** (recurso criado mas resposta perdida): mitigado por tag de idempotência +
  reconciliação por GET; nunca retry cego de criação.
- **Vazamento de token:** mitigado por redação no transport, sanitização no AuditLog, e nunca enviar ao front.
- **Ativação acidental:** mitigado por endpoint separado, papel elevado, confirmação e re-checagem.
- **Gasto não intencional:** mitigado por PAUSED-sempre, dois interruptores (DRY_RUN + WRITE_ENABLED),
  limites re-checados na ativação, e pausa de emergência sempre disponível.

### Ordem de implementação sugerida (cada passo testado antes do próximo)
1. Config/flags (§2) + `.env.example` + estender `Settings`.
2. Modelo de dados + migração Alembic (§8).
3. `WriteGraphTransport` + extração de `transport_base.py` + erros tipados (§3).
4. `RealMetaWriteClient` (implementar stub) com mock httpx (§3) + testes unitários.
5. Guards novos + `run_all_guards(mode="real")` + endurecimento de `min_config` (§1).
6. Workflow por etapas + `publish_real()` + task Celery + reconciliação (§4/§5).
7. Endpoints (§9) incl. status/refresh.
8. Ativação manual + pausa + pausa de emergência (§6).
9. Credenciais: leitura de `IntegrationCredential`, health check de escopos, expiração/rotação (§7).
10. Frontend (§10).
11. Testes de integração ponta-a-ponta com `META_PROVIDER=mock` (§11).
12. Docs (`META_SETUP.md`, README, SECURITY.md) + procedimento de teste ao vivo (§12).

### Entregáveis da Fase 6
Código + migração + testes (mock, sem custo) + docs atualizadas, com `DRY_RUN=true` e
`META_WRITE_ENABLED=false` como **default seguro** do repositório.
