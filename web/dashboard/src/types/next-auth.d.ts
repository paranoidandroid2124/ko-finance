import { DefaultSession, DefaultUser } from "next-auth";

declare module "next-auth" {
  interface User extends DefaultUser {
    plan?: "free" | "starter" | "pro" | "enterprise";
    role?: "user" | "admin";
    accessToken?: string;
    refreshToken?: string;
    sessionId?: string;
    sessionToken?: string;
    accessTokenExpires?: number;
    expiresIn?: number;
    onboardingRequired?: boolean;
  }

  interface JWT {
    sub?: string;
    plan?: "free" | "starter" | "pro" | "enterprise";
    role?: "user" | "admin";
    accessToken?: string;
    refreshToken?: string;
    sessionId?: string;
    sessionToken?: string;
    accessTokenExpires?: number | null;
    error?: string;
    onboardingRequired?: boolean;
  }

  interface Session {
    user: {
      id: string;
      plan: "free" | "starter" | "pro" | "enterprise";
      role?: "user" | "admin";
      onboardingRequired?: boolean;
    } & DefaultSession["user"];
    accessToken?: string;
    refreshToken?: string;
    sessionId?: string;
    sessionToken?: string;
    accessTokenExpires?: number | null;
    error?: string;
    onboardingRequired?: boolean;
    orgId?: string;
  }
}
