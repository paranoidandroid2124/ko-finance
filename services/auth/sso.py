"""SAML/OIDC single sign-on helpers."""

from __future__ import annotations

from .common import (
    OidcAuthorizeResult,
    RequestContext,
    build_oidc_authorize_url,
    complete_oidc_login,
    consume_saml_assertion,
    generate_saml_metadata,
)

__all__ = [
    "OidcAuthorizeResult",
    "RequestContext",
    "build_oidc_authorize_url",
    "complete_oidc_login",
    "consume_saml_assertion",
    "generate_saml_metadata",
]
