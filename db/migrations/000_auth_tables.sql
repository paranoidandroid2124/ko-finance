CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS "users" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "name" TEXT,
    "email" TEXT UNIQUE,
    "emailVerified" TIMESTAMPTZ,
    "image" TEXT
);

CREATE TABLE IF NOT EXISTS "accounts" (
    "id" SERIAL PRIMARY KEY,
    "userId" UUID NOT NULL REFERENCES "users"("id") ON DELETE CASCADE,
    "type" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "providerAccountId" TEXT NOT NULL,
    "refresh_token" TEXT,
    "access_token" TEXT,
    "expires_at" BIGINT,
    "token_type" TEXT,
    "scope" TEXT,
    "id_token" TEXT,
    "session_state" TEXT,
    CONSTRAINT "accounts_provider_providerAccountId_key" UNIQUE ("provider", "providerAccountId")
);

CREATE TABLE IF NOT EXISTS "sessions" (
    "id" SERIAL PRIMARY KEY,
    "sessionToken" TEXT UNIQUE NOT NULL,
    "userId" UUID NOT NULL REFERENCES "users"("id") ON DELETE CASCADE,
    "expires" TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS "verification_token" (
    "identifier" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "expires" TIMESTAMPTZ NOT NULL,
    CONSTRAINT "verification_token_pkey" PRIMARY KEY ("identifier", "token")
);
