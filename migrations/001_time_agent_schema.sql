-- ============================================================
-- Migration: 001_time_agent_schema.sql
-- Description: Adds schema models and alters execution_events
--              for Time Agent V1 Conversational Execution-Reporting.
-- ============================================================

-- 1. Alter execution_events columns to nullable (allows Mode B pure conversational events)
ALTER TABLE execution_events ALTER COLUMN artifact_id DROP NOT NULL;
ALTER TABLE execution_events ALTER COLUMN source_report_id DROP NOT NULL;
ALTER TABLE execution_events ALTER COLUMN source_document_name DROP NOT NULL;
ALTER TABLE execution_events ALTER COLUMN storage_key DROP NOT NULL;
ALTER TABLE execution_events ALTER COLUMN file_sha256 DROP NOT NULL;
ALTER TABLE execution_events ALTER COLUMN page_number DROP NOT NULL;

-- 2. Add new columns to execution_events
ALTER TABLE execution_events ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) NOT NULL DEFAULT 'ARTIFACT';
ALTER TABLE execution_events ADD COLUMN IF NOT EXISTS conversation_id VARCHAR(36);
ALTER TABLE execution_events ADD COLUMN IF NOT EXISTS message_id VARCHAR(36);

-- 3. Create conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id VARCHAR(100) NOT NULL,
    active_activity_id VARCHAR(36) REFERENCES activities(id) ON DELETE SET NULL,
    active_event_id VARCHAR(36) REFERENCES execution_events(id) ON DELETE SET NULL,
    clarification_turns INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- 4. Create conversation_messages table
CREATE TABLE IF NOT EXISTS conversation_messages (
    id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    message_metadata TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- 5. Create update_proposals table (with RESTRICT on event and activity for audit safety)
CREATE TABLE IF NOT EXISTS update_proposals (
    id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    event_id VARCHAR(36) NOT NULL REFERENCES execution_events(id) ON DELETE RESTRICT,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    matched_activity_id VARCHAR(36) NOT NULL REFERENCES activities(id) ON DELETE RESTRICT,
    proposed_state TEXT NOT NULL,
    baseline_activity_state TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    confirmed_by VARCHAR(100),
    confirmed_at TIMESTAMP WITHOUT TIME ZONE,
    consumed_at TIMESTAMP WITHOUT TIME ZONE
);

-- 6. Foreign key linkages
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_events_conversation'
    ) THEN
        ALTER TABLE execution_events ADD CONSTRAINT fk_events_conversation
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_events_message'
    ) THEN
        ALTER TABLE execution_events ADD CONSTRAINT fk_events_message
            FOREIGN KEY (message_id) REFERENCES conversation_messages(id) ON DELETE SET NULL;
    END IF;
END $$;

-- 7. Performance indexes
CREATE INDEX IF NOT EXISTS ix_conversations_proj_status ON conversations(project_id, status);
CREATE INDEX IF NOT EXISTS ix_conversation_messages_conv_created ON conversation_messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS ix_update_proposals_conv ON update_proposals(conversation_id, status);
CREATE INDEX IF NOT EXISTS ix_execution_events_conv ON execution_events(conversation_id);
