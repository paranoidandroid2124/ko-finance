#!/usr/bin/env python3
"""Clean up .env files by removing deprecated variables."""

import re
from pathlib import Path

# Variables to remove completely
VARS_TO_REMOVE = {
    # POSTGRES individual vars (replaced by DATABASE_URL)
    "POSTGRES_SERVER",
    "POSTGRES_PORT", 
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    # LLM model variables (commented out in .env.example, use litellm_config.yaml)
    "LLM_CLASSIFICATION_MODEL",
    "LLM_SUMMARY_MODEL",
    "LLM_EXTRACTION_MODEL",
    "LLM_SELF_CHECK_MODEL",
    "LLM_NEWS_MODEL",
    "LLM_RAG_MODEL",
    "LLM_QUALITY_FALLBACK_MODEL",
    "LLM_GUARD_JUDGE_MODEL",
    "LLM_ROUTER_MODEL",
    "LLM_QUERY_CLASSIFIER_MODEL",
    "LLM_REPORT_MODEL",
    # Other deprecated
    "GEMINI_API_KEY",  # If not using Gemini
    # Watchlist
    "WATCHLIST_PERSONAL_NOTE_MAX_CALLS",
    "WATCHLIST_PERSONAL_NOTE_CACHE_SECONDS",
    "WATCHLIST_PERSONAL_NOTE_MIN_INTERVAL_SECONDS",
    "WATCHLIST_PERSONAL_NOTE_TASK_TIMEOUT_SECONDS",
    # Table Extraction
    "TABLE_EXTRACTION_MAX_PAGES",
    "TABLE_EXTRACTION_TAT_SECONDS",
    "TABLE_EXTRACTION_OUTPUT_DIR",
    "TABLE_EXTRACTION_WRITE_ARTIFACTS",
    "TABLE_EXTRACTION_TARGET_TYPES",
    "TABLE_EXTRACTION_MAX_TABLES",
    "TABLE_EXTRACTION_INCLUDE_UNKNOWN",
    # Telegram
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_NOTIFY_POS_NEG_ONLY",
    # Enterprise Auth (SAML/OIDC/SCIM)
    "AUTH_SAML_ENABLED",
    "AUTH_SAML_SP_ENTITY_ID",
    "AUTH_SAML_ACS_URL",
    "AUTH_SAML_METADATA_URL",
    "AUTH_SAML_SP_CERT",
    "AUTH_SAML_IDP_ENTITY_ID",
    "AUTH_SAML_IDP_SSO_URL",
    "AUTH_SAML_IDP_CERT",
    "AUTH_SAML_EMAIL_ATTRIBUTE",
    "AUTH_SAML_NAME_ATTRIBUTE",
    "AUTH_SAML_ORG_ATTRIBUTE",
    "AUTH_SAML_ROLE_ATTRIBUTE",
    "AUTH_SAML_DEFAULT_ORG_SLUG",
    "AUTH_SAML_DEFAULT_RBAC_ROLE",
    "AUTH_SAML_ROLE_MAPPING",
    "AUTH_SAML_AUTO_PROVISION_ORG",
    "AUTH_SAML_DEFAULT_PLAN_TIER",
    "AUTH_SAML_CLOCK_SKEW_SECONDS",
    "AUTH_OIDC_ENABLED",
    "AUTH_OIDC_CLIENT_ID",
    "AUTH_OIDC_CLIENT_SECRET",
    "AUTH_OIDC_AUTHORIZATION_URL",
    "AUTH_OIDC_TOKEN_URL",
    "AUTH_OIDC_USERINFO_URL",
    "AUTH_OIDC_REDIRECT_URI",
    "AUTH_OIDC_SCOPES",
    "AUTH_OIDC_ORG_CLAIM",
    "AUTH_OIDC_ROLE_CLAIM",
    "AUTH_OIDC_PLAN_CLAIM",
    "AUTH_OIDC_EMAIL_CLAIM",
    "AUTH_OIDC_NAME_CLAIM",
    "AUTH_OIDC_DEFAULT_RBAC_ROLE",
    "AUTH_OIDC_ROLE_MAPPING",
    "AUTH_OIDC_DEFAULT_PLAN_TIER",
    "AUTH_OIDC_AUTO_PROVISION_ORG",
    "SCIM_BEARER_TOKEN",
    "SCIM_MAX_PAGE_SIZE",
    "SCIM_AUTO_PROVISION_ORG",
    "AUTH_SSO_STATE_SECRET",
    "AUTH_SSO_STATE_TTL_SECONDS",
    "SSO_PROVIDER_CACHE_TTL_SECONDS",
    # Email & PagerDuty (Phase 6)
    "ALERT_EMAIL_PROVIDER",
    "ALERT_EMAIL_FROM",
    "NHN_APP_KEY",
    "NHN_SECRET_KEY",
    "NHN_EMAIL_BASE_URL",
    "NHN_SENDER_NAME",
    "NHN_SENDER_ADDRESS",
    "NHN_EMAIL_TIMEOUT",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_USE_TLS",
    "ALERTS_FAILURE_EMAIL_TARGETS",
    "ALERTS_FAILURE_EMAIL_SUBJECT",
    "PAGERDUTY_ROUTING_KEY",
    # Compliance & Retention (Phase 6)
    "RETENTION_AUDIT_LOG_DAYS",
    "RETENTION_CHAT_SESSION_DAYS",
    "RETENTION_CHAT_AUDIT_DAYS",
    "RETENTION_DIGEST_SNAPSHOT_DAYS",
    "RETENTION_DIGEST_LOG_DAYS",
    "RETENTION_ALERT_DELIVERY_DAYS",
    "RETENTION_EVIDENCE_SNAPSHOT_DAYS",
    "RETENTION_NOTEBOOK_SHARE_DAYS",
    "DSAR_EXPORT_DIR",
    "DSAR_AUDIT_EXPORT_LIMIT",
    # Langfuse (Phase 7)
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
    # Admin (Phase 8)
    "ADMIN_API_TOKENS",
    "ADMIN_API_TOKEN",
    "ADMIN_SESSION_TTL_SECONDS",
    "ADMIN_SESSION_COOKIE_NAME",
    "ADMIN_SESSION_COOKIE_SAMESITE",
    "ADMIN_SESSION_COOKIE_SECURE",
    "GOOGLE_ADMIN_CLIENT_ID",
    "GOOGLE_ADMIN_ALLOWED_DOMAIN",
    "ADMIN_ALLOWED_EMAILS",
    "ADMIN_MFA_SECRETS",
    "ADMIN_REQUIRE_MFA",
}

def clean_env_file(file_path: Path) -> tuple[int, int]:
    """Clean a single .env file. Returns (lines_before, lines_after)."""
    if not file_path.exists():
        print(f"⏭️  Skipping {file_path} (not found)")
        return 0, 0
    
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    original_count = len(lines)
    
    cleaned_lines = []
    removed_vars = []
    
    for line in lines:
        # Check if this line defines a variable to remove
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            match = re.match(r'^([A-Z_][A-Z0-9_]*)=', stripped)
            if match:
                var_name = match.group(1)
                if var_name in VARS_TO_REMOVE:
                    removed_vars.append(var_name)
                    continue  # Skip this line
        
        cleaned_lines.append(line)
    
    if removed_vars:
        # Write cleaned content
        file_path.write_text("".join(cleaned_lines), encoding="utf-8")
        print(f"✅  Cleaned {file_path.name}:")
        print(f"   Removed {len(removed_vars)} variables: {', '.join(sorted(removed_vars))}")
    else:
        print(f"✓  {file_path.name} - no deprecated variables found")
    
    return original_count, len(cleaned_lines)

def main():
    """Clean all .env files."""
    base_dir = Path(__file__).parent.parent
    
    files_to_clean = [
        base_dir / ".env",
        base_dir / ".env.local",
        base_dir / "web" / "dashboard" / ".env.local",
    ]
    
    print("🧹 Starting .env files cleanup...\n")
    
    total_before = 0
    total_after = 0
    
    for file_path in files_to_clean:
        before, after = clean_env_file(file_path)
        total_before += before
        total_after += after
        print()
    
    print(f"📊 Summary:")
    print(f"   Total lines before: {total_before}")
    print(f"   Total lines after:  {total_after}")
    print(f"   Lines removed:      {total_before - total_after}")
    print(f"\n✨ Cleanup complete!")

if __name__ == "__main__":
    main()
