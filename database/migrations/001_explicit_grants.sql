-- ==============================================================================
-- VAL MIGRATION 001: EXPLICIT GRANTS FOR ALL TABLES
-- Safe to run on existing Supabase databases to grant required permissions
-- to 'postgres', 'service_role', 'authenticated', and 'anon' roles.
-- ==============================================================================

-- 1. Schema Usage
GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;

-- 2. Sequence Grants
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres, service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated, anon;

-- 3. Explicit Table-by-Table Grants

-- organizations
DO $$ BEGIN
    GRANT ALL ON TABLE public.organizations TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.organizations TO authenticated;
    GRANT SELECT ON TABLE public.organizations TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- users
DO $$ BEGIN
    GRANT ALL ON TABLE public.users TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.users TO authenticated;
    GRANT SELECT ON TABLE public.users TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- agents
DO $$ BEGIN
    GRANT ALL ON TABLE public.agents TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.agents TO authenticated;
    GRANT SELECT ON TABLE public.agents TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- agent_versions
DO $$ BEGIN
    GRANT ALL ON TABLE public.agent_versions TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.agent_versions TO authenticated;
    GRANT SELECT ON TABLE public.agent_versions TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- tasks
DO $$ BEGIN
    GRANT ALL ON TABLE public.tasks TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.tasks TO authenticated;
    GRANT SELECT ON TABLE public.tasks TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- tools
DO $$ BEGIN
    GRANT ALL ON TABLE public.tools TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.tools TO authenticated;
    GRANT SELECT ON TABLE public.tools TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- policies
DO $$ BEGIN
    GRANT ALL ON TABLE public.policies TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.policies TO authenticated;
    GRANT SELECT ON TABLE public.policies TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- memory_records
DO $$ BEGIN
    GRANT ALL ON TABLE public.memory_records TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.memory_records TO authenticated;
    GRANT SELECT ON TABLE public.memory_records TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- knowledge_items
DO $$ BEGIN
    GRANT ALL ON TABLE public.knowledge_items TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.knowledge_items TO authenticated;
    GRANT SELECT ON TABLE public.knowledge_items TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- learning_objectives
DO $$ BEGIN
    GRANT ALL ON TABLE public.learning_objectives TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.learning_objectives TO authenticated;
    GRANT SELECT ON TABLE public.learning_objectives TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- curricula
DO $$ BEGIN
    GRANT ALL ON TABLE public.curricula TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.curricula TO authenticated;
    GRANT SELECT ON TABLE public.curricula TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- approvals
DO $$ BEGIN
    GRANT ALL ON TABLE public.approvals TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.approvals TO authenticated;
    GRANT SELECT ON TABLE public.approvals TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- audit_logs (Immutable: standard roles get SELECT and INSERT only)
DO $$ BEGIN
    GRANT ALL ON TABLE public.audit_logs TO postgres, service_role;
    GRANT SELECT, INSERT ON TABLE public.audit_logs TO authenticated;
    GRANT SELECT ON TABLE public.audit_logs TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- experiments
DO $$ BEGIN
    GRANT ALL ON TABLE public.experiments TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.experiments TO authenticated;
    GRANT SELECT ON TABLE public.experiments TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- events
DO $$ BEGIN
    GRANT ALL ON TABLE public.events TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.events TO authenticated;
    GRANT SELECT ON TABLE public.events TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- conversations
DO $$ BEGIN
    GRANT ALL ON TABLE public.conversations TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.conversations TO authenticated;
    GRANT SELECT ON TABLE public.conversations TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- messages
DO $$ BEGIN
    GRANT ALL ON TABLE public.messages TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.messages TO authenticated;
    GRANT SELECT ON TABLE public.messages TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- projects
DO $$ BEGIN
    GRANT ALL ON TABLE public.projects TO postgres, service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.projects TO authenticated;
    GRANT SELECT ON TABLE public.projects TO anon;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- 4. Schema-wide Blanket Grants
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

-- 5. Future Default Privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO anon;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO authenticated, anon;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON ROUTINES TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON ROUTINES TO authenticated;
