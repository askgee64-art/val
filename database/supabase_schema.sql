-- ==============================================================================
-- VAL SUPABASE POSTGRESQL SCHEMA (v1.0)
-- Aligned with Document 21 (Database Design), Document 09, Document 35, Document 36
-- Supports multi-tenancy, Row Level Security (RLS), and pgvector embeddings
-- ==============================================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 2. ORGANIZATIONS (TENANTS)
CREATE TABLE IF NOT EXISTS public.organizations (
    org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
    plan_tier TEXT NOT NULL DEFAULT 'internal' CHECK (plan_tier IN ('internal', 'customer_standard', 'customer_enterprise')),
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 3. USERS (FOUNDER & OPERATORS)
CREATE TABLE IF NOT EXISTS public.users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'operator' CHECK (role IN ('founder', 'operator', 'viewer', 'customer_admin')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invited', 'disabled')),
    mfa_enabled BOOLEAN NOT NULL DEFAULT false,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 4. AGENTS (VAL CORE & SPECIALIZED AGENTS)
CREATE TABLE IF NOT EXISTS public.agents (
    agent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    parent_agent_id UUID REFERENCES public.agents(agent_id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0.0',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('draft', 'testing', 'active', 'suspended', 'retired')),
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
    knowledge_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by UUID REFERENCES public.users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    retired_at TIMESTAMPTZ,
    CONSTRAINT uq_agent_org_name UNIQUE (org_id, name)
);

-- 5. AGENT VERSIONS (AUDITABLE CONFIG SNAPSHOTS)
CREATE TABLE IF NOT EXISTS public.agent_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES public.agents(agent_id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    config_snapshot JSONB NOT NULL,
    changelog TEXT,
    created_by UUID REFERENCES public.users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_agent_version UNIQUE (agent_id, version)
);

-- 6. TASKS (OBJECTIVES & PLAN STEPS)
CREATE TABLE IF NOT EXISTS public.tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    agent_id UUID REFERENCES public.agents(agent_id) ON DELETE SET NULL,
    parent_task_id UUID REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'planning', 'running', 'waiting_approval', 'succeeded', 'failed', 'cancelled', 'paused')),
    priority INT NOT NULL DEFAULT 0,
    input JSONB,
    result JSONB,
    error JSONB,
    plan JSONB,
    requires_approval BOOLEAN NOT NULL DEFAULT false,
    approval_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    timeout_at TIMESTAMPTZ
);

-- 7. TOOLS REGISTRY
CREATE TABLE IF NOT EXISTS public.tools (
    tool_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_schema JSONB,
    risk_class TEXT NOT NULL DEFAULT 'low' CHECK (risk_class IN ('low', 'medium', 'high')),
    required_permission_level INT NOT NULL DEFAULT 2 CHECK (required_permission_level BETWEEN 0 AND 4),
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 8. PERMISSIONS & POLICIES
CREATE TABLE IF NOT EXISTS public.policies (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    action TEXT NOT NULL,
    effect TEXT NOT NULL DEFAULT 'allow' CHECK (effect IN ('allow', 'deny')),
    conditions JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 9. SCOPED MEMORY RECORDS (WITH PGVECTOR EMBEDDINGS)
CREATE TABLE IF NOT EXISTS public.memory_records (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('working', 'short_term', 'long_term', 'user', 'agent', 'project', 'company')),
    scope_id UUID,
    key TEXT,
    content JSONB NOT NULL,
    importance REAL NOT NULL DEFAULT 0.5,
    embedding vector(1536), -- Compatible with OpenAI / Gemini embeddings
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 10. KNOWLEDGE ITEMS & FOUNDER TEACHINGS
CREATE TABLE IF NOT EXISTS public.knowledge_items (
    knowledge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_url TEXT,
    source_type TEXT NOT NULL DEFAULT 'human' CHECK (source_type IN ('web', 'doc', 'api', 'human', 'founder_teaching')),
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_score REAL NOT NULL DEFAULT 0.5,
    embedding vector(1536),
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 11. LEARNING OBJECTIVES & CURRICULA (SECTION 14)
CREATE TABLE IF NOT EXISTS public.learning_objectives (
    objective_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    agent_id UUID REFERENCES public.agents(agent_id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('draft', 'generating_curriculum', 'in_progress', 'evaluating', 'ready_to_teach', 'completed', 'paused')),
    progress_score REAL NOT NULL DEFAULT 0.0 CHECK (progress_score BETWEEN 0.0 AND 100.0),
    current_topic TEXT,
    detected_weaknesses JSONB NOT NULL DEFAULT '[]'::jsonb,
    teaching_readiness REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS public.curricula (
    curriculum_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    objective_id UUID NOT NULL REFERENCES public.learning_objectives(objective_id) ON DELETE CASCADE,
    topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    rubric JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 12. LEVEL 4 APPROVAL GATES (FOUNDER CONTROL)
CREATE TABLE IF NOT EXISTS public.approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    task_id UUID REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    requested_by UUID,
    action_type TEXT NOT NULL,
    action_payload JSONB NOT NULL,
    risk_level INT NOT NULL DEFAULT 4,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    decided_by UUID REFERENCES public.users(user_id) ON DELETE SET NULL,
    decision_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    decided_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

-- 13. IMMUTABLE AUDIT LOGS (TABLE 11 & MASTER SPEC §11)
CREATE TABLE IF NOT EXISTS public.audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'val', 'system_agent', 'system', 'test')),
    actor_id UUID,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Disallow updates or deletes on audit_logs at PostgreSQL level
CREATE OR REPLACE FUNCTION public.fn_prevent_audit_tampering()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is immutable — updates and deletes are strictly prohibited.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_no_update ON public.audit_logs;
CREATE TRIGGER trg_audit_no_update
    BEFORE UPDATE OR DELETE ON public.audit_logs
    FOR EACH ROW EXECUTE FUNCTION public.fn_prevent_audit_tampering();

-- 14. EXPERIMENTS & SELF-IMPROVEMENT (SECTION 16)
CREATE TABLE IF NOT EXISTS public.experiments (
    experiment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(org_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'running', 'passed', 'failed', 'approved', 'rejected', 'merged')),
    baseline_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    experiment_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    sandbox_path TEXT,
    founder_approval_id UUID REFERENCES public.approvals(approval_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ
);

-- 15. EVENTS STREAM
CREATE TABLE IF NOT EXISTS public.events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- ==============================================================================
-- INDEXES FOR SCALE
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_agents_org_status ON public.agents (org_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_org_status ON public.tasks (org_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_desc ON public.tasks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_approvals_pending ON public.approvals (org_id, status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_audit_org_created ON public.audit_logs (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_scope ON public.memory_records (org_id, scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_learning_status ON public.learning_objectives (org_id, status);

-- pgvector cosine distance index
CREATE INDEX IF NOT EXISTS idx_memory_vector ON public.memory_records USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_knowledge_vector ON public.knowledge_items USING hnsw (embedding vector_cosine_ops);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_objectives ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.experiments ENABLE ROW LEVEL SECURITY;

-- Helper to extract org_id from JWT in Supabase
CREATE OR REPLACE FUNCTION public.current_org_id() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('request.jwt.claims', true)::json->>'org_id', '')::UUID;
$$ LANGUAGE sql STABLE;

-- Tenant Isolation Policies
CREATE POLICY tenant_isolation_agents ON public.agents
    FOR ALL USING (org_id = public.current_org_id() OR auth.role() = 'service_role');

CREATE POLICY tenant_isolation_tasks ON public.tasks
    FOR ALL USING (org_id = public.current_org_id() OR auth.role() = 'service_role');

CREATE POLICY tenant_isolation_memory ON public.memory_records
    FOR ALL USING (org_id = public.current_org_id() OR auth.role() = 'service_role');

CREATE POLICY tenant_isolation_knowledge ON public.knowledge_items
    FOR ALL USING (org_id = public.current_org_id() OR auth.role() = 'service_role');

CREATE POLICY tenant_isolation_learning ON public.learning_objectives
    FOR ALL USING (org_id = public.current_org_id() OR auth.role() = 'service_role');

CREATE POLICY tenant_isolation_approvals ON public.approvals
    FOR ALL USING (org_id = public.current_org_id() OR auth.role() = 'service_role');

-- Realtime publication for dashboard
ALTER PUBLICATION supabase_realtime ADD TABLE public.tasks, public.approvals, public.events, public.agents, public.learning_objectives;
