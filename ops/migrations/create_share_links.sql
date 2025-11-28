CREATE TABLE IF NOT EXISTS share_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token VARCHAR(64) NOT NULL UNIQUE,
    resource_type VARCHAR(32) NOT NULL CHECK (resource_type IN ('chat_session', 'report')),
    resource_id UUID NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    expires_at TIMESTAMPTZ,
    view_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_share_links_token ON share_links(token);
CREATE INDEX IF NOT EXISTS idx_share_links_resource ON share_links(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_share_links_created_by ON share_links(created_by);
