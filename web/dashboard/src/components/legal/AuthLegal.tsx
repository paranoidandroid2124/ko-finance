"use client";

import { LegalText } from "./LegalText";

export function AuthSignupHelper({ className }: { className?: string }) {
  return (
    <LegalText
      section="auth"
      item="signupHelper"
      as="div"
      className={className ?? "text-xs text-text-secondaryLight dark:text-text-secondaryDark"}
    />
  );
}

export function AuthTermsCheckboxLabel() {
  return <LegalText section="auth" item="termsCheckbox" as="span" />;
}

export function AuthPrivacyCheckboxLabel() {
  return <LegalText section="auth" item="privacyCheckbox" as="span" />;
}

export function AuthMarketingCheckboxLabel() {
  return <LegalText section="auth" item="marketingCheckbox" as="span" />;
}

