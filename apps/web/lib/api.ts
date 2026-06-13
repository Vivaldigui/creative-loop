const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string;
}

export interface ProductOut {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  status: string;
  is_fictitious: boolean;
}

export interface SnapshotOut {
  id: string;
  date_start: string | null;
  date_stop: string | null;
  impressions: number | null;
  reach: number | null;
  spend: number | null;
  clicks: number | null;
  link_clicks: number | null;
  ctr: number | null;
  cpc: number | null;
  cpm: number | null;
  purchases: number | null;
  leads: number | null;
  adds_to_cart: number | null;
  landing_page_views: number | null;
  purchase_value: number | null;
  roas: number | null;
  roas_source: string | null;
  currency: string | null;
  attribution_window: string | null;
  level: string | null;
  normalization_version: string | null;
  is_fictitious: boolean;
}

export interface CreativeOut {
  id: string;
  external_id: string;
  name: string | null;
  title: string | null;
  body: string | null;
  cta_type: string | null;
  link_url: string | null;
  image_hash: string | null;
  image_url: string | null;
  source: string | null;
}

export interface AdSetOut {
  id: string;
  external_id: string;
  name: string;
  optimization_goal: string | null;
  effective_status: string | null;
}

export interface SourceAdOut {
  id: string;
  external_id: string | null;
  name: string;
  headline: string | null;
  body_text: string | null;
  cta: string | null;
  ad_format: string | null;
  placement: string | null;
  objective: string | null;
  status: string;
  effective_status: string | null;
  configured_status: string | null;
  performance_label: string | null;
  is_fictitious: boolean;
  source: string | null;
  last_synced_at: string | null;
  snapshots: SnapshotOut[];
  source_adset: AdSetOut | null;
  source_creative: CreativeOut | null;
}

export interface ObservationItem {
  text: string;
  category: string;
  source?: string;
}

export interface MetricFactItem {
  text: string;
  metric: string;
  value?: number | null;
}

export interface PerformanceHypothesisItem {
  statement: string;
  primary_variable: string;
  confidence: number;
}

export interface AnalysisOut {
  id: string;
  source_ad_id: string;
  provider: string;
  model_used: string | null;
  status: string;
  analysis_version: number;
  media_kind: string | null;
  visual_summary: string | null;
  observations: ObservationItem[] | null;
  metric_facts: MetricFactItem[] | null;
  limitations: string[] | null;
  strengths: string[] | null;
  weaknesses: string[] | null;
  performance_hypotheses: PerformanceHypothesisItem[] | null;
  elements_to_test: string[] | null;
  policy_risks: string[] | null;
  confidence: number | null;
  is_fictitious: boolean;
  repaired: boolean;
  estimated_cost_usd: number | null;
  latency_ms: number | null;
}

export interface AnalysisDetailOut extends AnalysisOut {
  input_hash: string | null;
  composition: Record<string, unknown> | null;
  hierarchy: Record<string, unknown> | null;
  product_presentation: Record<string, unknown> | null;
  color_and_lighting: Record<string, unknown> | null;
  text_analysis: Record<string, unknown> | null;
  attention_elements: string[] | null;
  elements_to_preserve: string[] | null;
  request_metadata: Record<string, unknown> | null;
  parameters: Record<string, unknown> | null;
  prompt_tokens: number | null;
  output_tokens: number | null;
  created_at: string | null;
}

export interface PromptVersionOut {
  id: string;
  template_id: string;
  source_ad_id: string | null;
  analysis_id: string | null;
  parent_version_id: string | null;
  version_number: number;
  prompt_text: string;
  structured_fields: Record<string, unknown> | null;
  diff_summary: string | null;
  change_reason: string | null;
  author_type: string;
  content_hash: string | null;
  target_model: string | null;
  status: string;
  is_fictitious: boolean;
  created_at: string | null;
}

export interface PromptTemplateOut {
  id: string;
  name: string;
  product_id: string | null;
  hypothesis_id: string | null;
  ad_format: string | null;
  objective: string | null;
  status: string;
  created_at: string | null;
}

export interface PromptTemplateDetailOut extends PromptTemplateOut {
  latest_version: PromptVersionOut | null;
  version_count: number;
}

export interface DiffOut {
  version_a: { id: string; version_number: number; [key: string]: unknown };
  version_b: { id: string; version_number: number; [key: string]: unknown };
  unified_diff: string;
  field_changes: Record<string, { before: unknown; after: unknown }>;
  changed_field_count: number;
}

export interface CreativeAssetOut {
  id: string;
  role: "original" | "derivative" | "thumbnail" | string;
  format_label: string | null;
  width: number | null;
  height: number | null;
  file_size_bytes: number | null;
  file_hash: string | null;
  fit_strategy: string | null;
  signed_url: string | null;
}

export interface GeneratedCreativeOut {
  id: string;
  prompt_version_id: string;
  provider: string;
  model_used: string | null;
  file_path: string | null;
  storage_key: string | null;
  storage_backend: string | null;
  file_hash: string | null;
  phash: string | null;
  width: number | null;
  height: number | null;
  file_size_bytes: number | null;
  mime_type: string | null;
  status: string;
  is_fictitious: boolean;
  estimated_cost_usd: number | null;
  variation_of_id: string | null;
  source_ad_id: string | null;
  assets: CreativeAssetOut[];
}

export interface CheckSummary {
  id: string;
  result: "PASS" | "WARNING" | "BLOCKED";
  findings_count: number;
  has_blocked: boolean;
  has_warning: boolean;
  checker_types: string[];
}

export interface ApprovalQueueItem {
  id: string;
  status: string;
  provider: string;
  model_used: string | null;
  storage_key: string | null;
  file_hash: string | null;
  width: number | null;
  height: number | null;
  is_fictitious: boolean;
  estimated_cost_usd: number | null;
  variation_of_id: string | null;
  source_ad_id: string | null;
  quality_check: CheckSummary | null;
  policy_check: CheckSummary | null;
  thumbnail_url: string | null;
  created_at: string | null;
}

export interface ApprovalDetailOut {
  id: string;
  status: string;
  provider: string;
  model_used: string | null;
  parameters: Record<string, unknown> | null;
  file_hash: string | null;
  phash: string | null;
  width: number | null;
  height: number | null;
  estimated_cost_usd: number | null;
  is_fictitious: boolean;
  variation_of_id: string | null;
  source_ad_id: string | null;
  prompt_version_id: string;
  prompt_text: string | null;
  prompt_version_number: number | null;
  prompt_diff_summary: string | null;
  prompt_change_reason: string | null;
  prompt_learning_used: string | null;
  quality_checks: Array<Record<string, unknown>>;
  policy_checks: Array<Record<string, unknown>>;
  assets: Array<Record<string, unknown>>;
  internal_notice: string;
  created_at: string | null;
}

export interface CheckResult {
  result: "PASS" | "WARNING" | "BLOCKED";
  findings: { rule: string; segment: string | null; matched_text: string; severity: string }[];
}

// ── Phase 6 — Real publish ────────────────────────────────────────────────────

export interface StepOut {
  id: string;
  state: string;
  meta_node_id: string | null;
  meta_request_id: string | null;
  is_recoverable: boolean;
  error_detail: string | null;
  created_at: string;
}

export interface RealPublishResponse {
  attempt_id: string;
  published_ad_id: string;
  status: string;
  workflow_state: string;
  meta_campaign_id: string | null;
  meta_adset_id: string | null;
  meta_ad_id: string | null;
  idempotency_tag: string | null;
  steps: StepOut[];
  checks: GuardCheckResult[];
  message: string;
}

export interface PublishStatusResponse {
  attempt_id: string;
  mode: string;
  result: string;
  workflow_state: string;
  meta_campaign_id: string | null;
  meta_adset_id: string | null;
  meta_ad_id: string | null;
  steps: StepOut[];
  error_detail: string | null;
}

export interface PublishedAdOut {
  id: string;
  creative_id: string;
  idempotency_key: string;
  idempotency_tag: string | null;
  dry_run: boolean;
  status: string;
  workflow_state: string;
  meta_campaign_id: string | null;
  meta_adset_id: string | null;
  meta_ad_id: string | null;
  requires_manual_review: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface ActivateResponse {
  id: string;
  status: string;
  message: string;
}

export interface PauseResponse {
  id: string;
  status: string;
  message: string;
}

// ── Phase 5 — Publish (DRY_RUN) ──────────────────────────────────────────────

export interface GuardCheckResult {
  code: string;
  severity: "pass" | "warning" | "blocked";
  passed: boolean;
  detail: string;
}

export interface SimulatedPublishResponse {
  dry_run: boolean;
  mode: string;
  note: string;
  simulated_campaign_id: string;
  simulated_adset_id: string;
  simulated_image_hash: string;
  simulated_ad_creative_id: string;
  simulated_ad_id: string;
  steps_simulated: string[];
  placeholders_present: string[];
}

export interface ValidateResponse {
  creative_id: string;
  passed: boolean;
  blocked_count: number;
  warning_count: number;
  checks: GuardCheckResult[];
  payload_preview: Record<string, unknown> | null;
  dry_run_mode: boolean;
}

export interface DryRunResponse {
  attempt_id: string;
  published_ad_id: string | null;
  dry_run: boolean;
  mode: string;
  idempotent: boolean;
  result: string;
  checks: GuardCheckResult[];
  simulated_response: SimulatedPublishResponse | null;
  payload: Record<string, unknown> | null;
  correlation_id: string;
  message: string;
}

export interface PublicationAttemptOut {
  id: string;
  creative_id: string;
  draft_id: string | null;
  idempotency_key: string;
  payload_hash: string;
  mode: string;
  correlation_id: string | null;
  result: string;
  simulated_response: SimulatedPublishResponse | null;
  checks: GuardCheckResult[] | null;
  error_detail: string | null;
  published_ad_id: string | null;
  created_at: string;
}

export interface SyncRunOut {
  id: string;
  account_external_id: string;
  kind: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  date_start: string | null;
  date_stop: string | null;
  campaigns_created: number;
  campaigns_updated: number;
  adsets_created: number;
  adsets_updated: number;
  ads_created: number;
  ads_updated: number;
  snapshots_created: number;
  snapshots_updated: number;
  assets_created: number;
  error_detail: string | null;
}

// ── Phase 7 — Experiments ─────────────────────────────────────────────────────

export interface ExperimentVariantOut {
  id: string;
  name: string;
  description: string | null;
  variant_role: string | null;
  hypothesis: string | null;
  prompt_version_id: string | null;
  published_ad_id: string | null;
  changed_variables: Record<string, unknown> | null;
  allocated_budget: number | null;
  is_fictitious: boolean;
  created_at: string | null;
}

export interface ExperimentOut {
  id: string;
  name: string;
  description: string | null;
  mode: string;
  hypothesis: string | null;
  primary_variable: string | null;
  status: string;
  evaluation_state: string | null;
  objective: string | null;
  product_id: string | null;
  placement: string | null;
  primary_metric: string | null;
  planned_budget: number | null;
  currency: string | null;
  window_start: string | null;
  window_end: string | null;
  started_at: string | null;
  ended_at: string | null;
  stop_reason: string | null;
  is_fictitious: boolean;
  variants: ExperimentVariantOut[];
  created_at: string | null;
  updated_at: string | null;
}

export interface EvaluationOut {
  id: string;
  experiment_id: string;
  evaluation_state: string;
  primary_metric: string | null;
  per_variant_result: Record<string, unknown> | null;
  confidence: number | null;
  causal_attribution: boolean;
  limitations: string[] | null;
  engine_version: string | null;
  evaluated_at: string | null;
}

export interface DecisionOut {
  id: string;
  experiment_id: string;
  evaluation_id: string | null;
  recommendation: string | null;
  suggested_action: string | null;
  executed_action: string | null;
  confidence: number | null;
  limitations: string[] | null;
  primary_metric: string | null;
  decided_at: string | null;
  created_at: string | null;
}

export interface VariantSnapshotOut {
  id: string;
  variant_id: string;
  date_start: string;
  date_stop: string;
  impressions: number | null;
  clicks: number | null;
  spend: number | null;
  ctr: number | null;
  cvr: number | null;
  roas: number | null;
  purchases: number | null;
  leads: number | null;
  is_matured: boolean;
  is_fictitious: boolean;
}

export interface LearningOut {
  id: string;
  observed_pattern: string;
  context: string | null;
  segment: string | null;
  objective: string | null;
  placement: string | null;
  format: string | null;
  confidence: number | null;
  status: string;
  responsible_type: string | null;
  period_start: string | null;
  period_end: string | null;
  sample_size: number | null;
  reviewed_at: string | null;
  review_comment: string | null;
  created_at: string | null;
}

export interface SuggestionOut {
  id: string;
  source_experiment_id: string | null;
  draft_experiment_id: string | null;
  hypothesis: string | null;
  primary_variable: string | null;
  rationale: string | null;
  diversity_score: number | null;
  status: string;
  selected_learning_ids: string[] | null;
  context_snapshot: Record<string, unknown> | null;
  reviewed_at: string | null;
  review_comment: string | null;
  created_at: string | null;
}

export interface AlertItem {
  level: string;
  code: string;
  message: string;
  entity_id: string | null;
  entity_type: string | null;
}

export interface DailyReportOut {
  report_date: string;
  period_start: string;
  period_end: string;
  total_spend: number | null;
  currency: string;
  running_experiments: number;
  evaluating_experiments: number;
  alerts: AlertItem[];
  ads_without_conversions: Record<string, unknown>[];
  rejected_ads: Record<string, unknown>[];
  experiments_with_issues: Record<string, unknown>[];
  generated_at: string;
}

export interface WeeklyReportOut {
  report_week: string;
  period_start: string;
  period_end: string;
  total_spend: number | null;
  currency: string;
  completed_experiments: Record<string, unknown>[];
  promising_patterns: Record<string, unknown>[];
  rejected_patterns: Record<string, unknown>[];
  new_learnings: Record<string, unknown>[];
  suggestions: Record<string, unknown>[];
  generated_at: string;
}

export interface MetricsOut {
  total_spend: number;
  total_impressions: number;
  total_clicks: number;
  total_purchases: number;
  total_leads: number;
  total_adds_to_cart: number;
  total_purchase_value: number;
  avg_roas: number;
  derived_roas: number | null;
  avg_ctr: number;
  avg_cpc: number;
  avg_cpm: number;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<UserOut>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
    logout: () => request<void>("/auth/logout", { method: "POST" }),
    me: () => request<UserOut>("/auth/me"),
  },

  products: {
    list: () => request<ProductOut[]>("/products"),
    create: (data: { name: string; description?: string; category?: string }) =>
      request<ProductOut>("/products", { method: "POST", body: JSON.stringify(data) }),
  },

  integrations: {
    test: (provider: "meta" | "openai" | "anthropic") =>
      request<{ provider: string; status: string; message?: string }>(`/integrations/${provider}/test`, { method: "POST" }),
    metaAccounts: () =>
      request<{ accounts: unknown[]; status: string; count: number }>("/integrations/meta/accounts"),
  },

  sourceAds: {
    list: (params?: {
      performance_label?: string;
      source?: string;
      objective?: string;
      effective_status?: string;
      is_fictitious?: boolean;
      limit?: number;
      offset?: number;
    }) => {
      const qs = params
        ? "?" + new URLSearchParams(
            Object.entries(params)
              .filter(([, v]) => v !== undefined && v !== null)
              .map(([k, v]) => [k, String(v)])
          ).toString()
        : "";
      return request<SourceAdOut[]>(`/source-ads${qs}`);
    },
    get: (id: string) => request<SourceAdOut>(`/source-ads/${id}`),
    insights: (id: string, limit?: number) =>
      request<SnapshotOut[]>(`/source-ads/${id}/insights${limit ? `?limit=${limit}` : ""}`),
    analyze: (id: string, force?: boolean) =>
      request<AnalysisOut>(`/source-ads/${id}/analyze`, {
        method: "POST",
        body: JSON.stringify({ force: force ?? false }),
      }),
    analyses: (id: string) => request<AnalysisOut[]>(`/source-ads/${id}/analyses`),
  },

  analyses: {
    get: (id: string) => request<AnalysisDetailOut>(`/analyses/${id}`),
  },

  sync: {
    history: (data?: { account_id?: string; date_start?: string; date_stop?: string }) =>
      request<{ sync_run_id: string; status: string; message: string }>("/sync/meta/history", {
        method: "POST",
        body: JSON.stringify(data ?? {}),
      }),
    incremental: (data?: { account_id?: string; days_back?: number }) =>
      request<{ sync_run_id: string; status: string; message: string }>("/sync/meta/incremental", {
        method: "POST",
        body: JSON.stringify(data ?? {}),
      }),
    runs: (limit?: number) =>
      request<SyncRunOut[]>(`/sync/meta/runs${limit ? `?limit=${limit}` : ""}`),
    run: (id: string) => request<SyncRunOut>(`/sync/meta/runs/${id}`),
  },

  metrics: {
    summary: (params?: { date_start?: string; date_stop?: string; source?: string }) => {
      const qs = params
        ? "?" + new URLSearchParams(
            Object.entries(params)
              .filter(([, v]) => v !== undefined && v !== null)
              .map(([k, v]) => [k, String(v)])
          ).toString()
        : "";
      return request<MetricsOut>(`/metrics${qs}`);
    },
    topAds: (metric?: string, limit?: number, source?: string) => {
      const params = new URLSearchParams();
      if (metric) params.set("metric", metric);
      if (limit) params.set("limit", String(limit));
      if (source) params.set("source", source);
      const qs = params.toString() ? `?${params}` : "";
      return request<{ id: string; name: string; performance_label: string | null; source: string | null; is_fictitious: boolean; [key: string]: unknown }[]>(`/metrics/top-ads${qs}`);
    },
  },

  prompts: {
    generate: (data: {
      source_ad_id?: string;
      analysis_id?: string;
      product_id?: string;
      hypothesis_id?: string;
      fields?: Record<string, string>;
      ad_format?: string;
      objective?: string;
      template_name?: string;
      author_type?: string;
      target_model?: string;
    }) => request<PromptVersionOut>("/prompts/generate", { method: "POST", body: JSON.stringify(data) }),
    list: (params?: { product_id?: string; objective?: string; ad_format?: string; limit?: number; offset?: number }) => {
      const qs = params
        ? "?" + new URLSearchParams(
            Object.entries(params)
              .filter(([, v]) => v !== undefined && v !== null)
              .map(([k, v]) => [k, String(v)])
          ).toString()
        : "";
      return request<PromptTemplateOut[]>(`/prompts${qs}`);
    },
    get: (templateId: string) => request<PromptTemplateDetailOut>(`/prompts/${templateId}`),
    revise: (templateId: string, data: {
      fields: Record<string, string>;
      change_reason: string;
      base_version_id?: string;
      author_type?: string;
      target_model?: string;
    }) =>
      request<PromptVersionOut>(`/prompts/${templateId}/revise`, { method: "POST", body: JSON.stringify(data) }),
    versions: (templateId: string) =>
      request<PromptVersionOut[]>(`/prompts/${templateId}/versions`),
  },

  promptVersions: {
    get: (versionId: string) => request<PromptVersionOut>(`/prompt-versions/${versionId}`),
    diff: (versionAId: string, versionBId: string) =>
      request<DiffOut>(`/prompt-versions/${versionAId}/diff/${versionBId}`),
  },

  creatives: {
    generate: (data: {
      prompt_version_id: string;
      width?: number;
      height?: number;
      quality?: string;
      n?: number;
      extra_formats?: string[];
      source_ad_id?: string;
    }) =>
      request<GeneratedCreativeOut>("/creatives", { method: "POST", body: JSON.stringify(data) }),
    list: (params?: { status?: string; prompt_version_id?: string; limit?: number; offset?: number }) => {
      const qs = params
        ? "?" + new URLSearchParams(
            Object.entries(params)
              .filter(([, v]) => v !== undefined && v !== null)
              .map(([k, v]) => [k, String(v)])
          ).toString()
        : "";
      return request<GeneratedCreativeOut[]>(`/creatives${qs}`);
    },
    get: (id: string) => request<GeneratedCreativeOut>(`/creatives/${id}`),
    qualityCheck: (id: string) =>
      request<{ result: string; findings: unknown[] }>(`/creatives/${id}/quality-check`, { method: "POST" }),
    policyCheck: (id: string) =>
      request<{ result: string; findings: unknown[]; internal_notice: string }>(`/creatives/${id}/policy-check`, { method: "POST" }),
    approve: (id: string, comment?: string, override_blocked?: boolean) =>
      request<{ status: string }>(`/creatives/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ comment, override_blocked: override_blocked ?? false }),
      }),
    reject: (id: string, comment: string) =>
      request<{ status: string }>(`/creatives/${id}/reject`, { method: "POST", body: JSON.stringify({ comment }) }),
    requestVariation: (id: string, comment: string, prompt_version_id?: string) =>
      request<{ status: string; new_creative_id: string }>(`/creatives/${id}/request-variation`, {
        method: "POST",
        body: JSON.stringify({ comment, prompt_version_id }),
      }),
  },

  approvals: {
    list: (params?: { include_blocked?: boolean; limit?: number; offset?: number }) => {
      const qs = params
        ? "?" + new URLSearchParams(
            Object.entries(params)
              .filter(([, v]) => v !== undefined && v !== null)
              .map(([k, v]) => [k, String(v)])
          ).toString()
        : "";
      return request<ApprovalQueueItem[]>(`/approvals${qs}`);
    },
    get: (id: string) => request<ApprovalDetailOut>(`/approvals/${id}`),
  },

  publish: {
    validate: (data: {
      creative_id: string;
      idempotency_key?: string;
      objective?: string;
      daily_budget_brl: number;
      optimization_goal?: string;
      landing_url?: string;
      campaign_name?: string;
      adset_name?: string;
      ad_name?: string;
      targeting?: Record<string, unknown>;
      experiment_id?: string;
    }) =>
      request<ValidateResponse>("/publish/meta/validate", {
        method: "POST",
        body: JSON.stringify({ idempotency_key: "validate_check", ...data }),
      }),

    dryRun: (data: {
      creative_id: string;
      idempotency_key: string;
      campaign_name?: string;
      adset_name?: string;
      ad_name?: string;
      objective?: string;
      daily_budget_brl: number;
      optimization_goal?: string;
      billing_event?: string;
      bid_strategy?: string;
      headline?: string;
      body_text?: string;
      cta_type?: string;
      landing_url?: string;
      tracking_params?: Record<string, string>;
      targeting?: Record<string, unknown>;
      placements?: string[];
      experiment_id?: string;
      draft_id?: string;
    }) =>
      request<DryRunResponse>("/publish/meta/dry-run", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    getAttempt: (id: string) =>
      request<PublicationAttemptOut>(`/publication-attempts/${id}`),

    listDrafts: (params?: { creative_id?: string; status?: string; limit?: number }) => {
      const qs = params
        ? "?" + new URLSearchParams(
            Object.entries(params)
              .filter(([, v]) => v !== undefined && v !== null)
              .map(([k, v]) => [k, String(v)])
          ).toString()
        : "";
      return request<{ id: string; creative_id: string; status: string; created_at: string }[]>(
        `/publish/meta/drafts${qs}`
      );
    },

    real: (data: {
      creative_id: string;
      idempotency_key: string;
      daily_budget_brl: number;
      landing_url: string;
      confirm_paused: boolean;
      campaign_name?: string;
      adset_name?: string;
      ad_name?: string;
      objective?: string;
      optimization_goal?: string;
      headline?: string;
      body_text?: string;
      cta_type?: string;
    }) =>
      request<RealPublishResponse>("/publish/meta", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    getAttemptStatus: (id: string) =>
      request<PublishStatusResponse>(`/publication-attempts/${id}/status`),
  },

  experiments: {
    list: (params?: { status?: string; mode?: string; product_id?: string; page?: number }) => {
      const qs = params
        ? "?" + new URLSearchParams(
            Object.entries(params)
              .filter(([, v]) => v !== undefined && v !== null)
              .map(([k, v]) => [k, String(v)])
          ).toString()
        : "";
      return request<{ items: ExperimentOut[]; total: number }>(`/experiments${qs}`);
    },
    get: (id: string) => request<ExperimentOut>(`/experiments/${id}`),
    create: (data: Record<string, unknown>) =>
      request<ExperimentOut>("/experiments", { method: "POST", body: JSON.stringify(data) }),
    start: (id: string) =>
      request<ExperimentOut>(`/experiments/${id}/start`, { method: "POST", body: JSON.stringify({ confirm: true }) }),
    stop: (id: string, stop_reason: string, notes?: string) =>
      request<ExperimentOut>(`/experiments/${id}/stop`, { method: "POST", body: JSON.stringify({ stop_reason, notes }) }),
    complete: (id: string) =>
      request<ExperimentOut>(`/experiments/${id}/complete`, { method: "POST" }),
    evaluate: (id: string, notes?: string) =>
      request<EvaluationOut>(`/experiments/${id}/evaluate`, { method: "POST", body: JSON.stringify({ notes }) }),
    evaluations: (id: string) => request<EvaluationOut[]>(`/experiments/${id}/evaluations`),
    metrics: (id: string, variant_id?: string) => {
      const qs = variant_id ? `?variant_id=${variant_id}` : "";
      return request<VariantSnapshotOut[]>(`/experiments/${id}/metrics${qs}`);
    },
    decisions: (id: string) => request<DecisionOut[]>(`/experiments/${id}/decisions`),
    createDecision: (id: string, data: Record<string, unknown>) =>
      request<DecisionOut>(`/experiments/${id}/decisions`, { method: "POST", body: JSON.stringify(data) }),
    suggestNextRound: (id: string) =>
      request<SuggestionOut>(`/experiments/${id}/suggest-next-round`, { method: "POST" }),
    suggestions: (id: string) => request<SuggestionOut[]>(`/experiments/${id}/suggestions`),
  },

  learnings: {
    list: (params?: { status?: string; product_id?: string; segment?: string; objective?: string; page?: number }) => {
      const qs = params
        ? "?" + new URLSearchParams(
            Object.entries(params)
              .filter(([, v]) => v !== undefined && v !== null)
              .map(([k, v]) => [k, String(v)])
          ).toString()
        : "";
      return request<LearningOut[]>(`/learnings${qs}`);
    },
    get: (id: string) => request<LearningOut>(`/learnings/${id}`),
    create: (data: Record<string, unknown>) =>
      request<LearningOut>("/learnings", { method: "POST", body: JSON.stringify(data) }),
    confirm: (id: string, comment?: string) =>
      request<LearningOut>(`/learnings/${id}/confirm`, { method: "POST", body: JSON.stringify({ comment }) }),
    reject: (id: string, comment: string) =>
      request<LearningOut>(`/learnings/${id}/reject`, { method: "POST", body: JSON.stringify({ comment }) }),
  },

  suggestions: {
    list: (params?: { status?: string }) => {
      const qs = params?.status ? `?status=${params.status}` : "";
      return request<SuggestionOut[]>(`/suggestions${qs}`);
    },
    get: (id: string) => request<SuggestionOut>(`/suggestions/${id}`),
    approve: (id: string, comment?: string) =>
      request<SuggestionOut>(`/suggestions/${id}/approve`, { method: "POST", body: JSON.stringify({ comment }) }),
    reject: (id: string, comment?: string) =>
      request<SuggestionOut>(`/suggestions/${id}/reject`, { method: "POST", body: JSON.stringify({ comment }) }),
  },

  reports: {
    daily: (report_date?: string) => {
      const qs = report_date ? `?report_date=${report_date}` : "";
      return request<DailyReportOut>(`/reports/daily${qs}`);
    },
    weekly: (week_start?: string) => {
      const qs = week_start ? `?week_start=${week_start}` : "";
      return request<WeeklyReportOut>(`/reports/weekly${qs}`);
    },
  },

  publishedAds: {
    list: (params?: { creative_id?: string; dry_run?: boolean; status?: string; limit?: number }) => {
      const qs = params
        ? "?" + new URLSearchParams(
            Object.entries(params)
              .filter(([, v]) => v !== undefined && v !== null)
              .map(([k, v]) => [k, String(v)])
          ).toString()
        : "";
      return request<PublishedAdOut[]>(`/published-ads${qs}`);
    },

    get: (id: string) => request<PublishedAdOut>(`/published-ads/${id}`),

    refreshStatus: (id: string) =>
      request<{ id: string; status: string; effective_status: string | null; message: string }>(
        `/published-ads/${id}/refresh-status`,
        { method: "POST" }
      ),

    activate: (id: string, confirmation: string) =>
      request<ActivateResponse>(`/published-ads/${id}/activate`, {
        method: "POST",
        body: JSON.stringify({ confirmation }),
      }),

    pause: (id: string) =>
      request<PauseResponse>(`/published-ads/${id}/pause`, { method: "POST" }),

    emergencyPause: (id: string) =>
      request<PauseResponse>(`/published-ads/${id}/emergency-pause`, { method: "POST" }),
  },
};
