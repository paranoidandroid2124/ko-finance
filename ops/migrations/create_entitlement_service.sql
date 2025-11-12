-- EntitlementService v1 schema: plan catalog + org subscriptions + quota usage

CREATE TABLE IF NOT EXISTS plans (
    id SERIAL PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION touch_plans_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_plans_updated_at ON plans;
CREATE TRIGGER trg_plans_updated_at
BEFORE UPDATE ON plans
FOR EACH ROW
EXECUTE FUNCTION touch_plans_updated_at();

CREATE TABLE IF NOT EXISTS plan_entitlements (
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (plan_id, key)
);

CREATE OR REPLACE FUNCTION touch_plan_entitlements_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_plan_entitlements_updated_at ON plan_entitlements;
CREATE TRIGGER trg_plan_entitlements_updated_at
BEFORE UPDATE ON plan_entitlements
FOR EACH ROW
EXECUTE FUNCTION touch_plan_entitlements_updated_at();

CREATE TABLE IF NOT EXISTS org_subscriptions (
    org_id UUID PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    status TEXT NOT NULL,
    current_period_end TIMESTAMPTZ NOT NULL,
    metadata JSONB NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_org_subscriptions_plan_id
    ON org_subscriptions(plan_id);

CREATE TABLE IF NOT EXISTS user_org_members (
    org_id UUID NOT NULL,
    user_id UUID NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_org_members_user_id
    ON user_org_members(user_id);

CREATE OR REPLACE FUNCTION touch_user_org_members_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_org_members_updated_at ON user_org_members;
CREATE TRIGGER trg_user_org_members_updated_at
BEFORE UPDATE ON user_org_members
FOR EACH ROW
EXECUTE FUNCTION touch_user_org_members_updated_at();

CREATE TABLE IF NOT EXISTS entitlement_usage_daily (
    org_id UUID NOT NULL,
    user_id UUID NOT NULL,
    action TEXT NOT NULL,
    day DATE NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, user_id, action, day)
);

CREATE INDEX IF NOT EXISTS idx_entitlement_usage_daily_action_day
    ON entitlement_usage_daily(action, day);
