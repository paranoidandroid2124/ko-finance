-- Extend signup_channel allowed values for SAML/OIDC/SCIM provisioning

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'users_signup_channel_check'
          AND conrelid = 'users'::regclass
    ) THEN
        ALTER TABLE "users" DROP CONSTRAINT users_signup_channel_check;
    END IF;
END $$;

ALTER TABLE "users"
    ADD CONSTRAINT users_signup_channel_check
    CHECK (
        signup_channel IN ('email','google','kakao','naver','admin_invite','saml','oidc','scim')
    );
