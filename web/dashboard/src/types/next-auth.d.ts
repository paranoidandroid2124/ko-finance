import NextAuth, { DefaultSession, DefaultUser } from "next-auth";

declare module "next-auth" {
  interface User extends DefaultUser {
    plan?: "free" | "pro" | "enterprise";
    role?: "user" | "admin";
    accessToken?: string;
    refreshToken?: string;
    sessionId?: string;
    sessionToken?: string;
    accessTokenExpires?: number;
    expiresIn?: number;
  }

  interface JWT {
    sub?: string;
    plan?: "free" | "pro" | "enterprise";
    role?: "user" | "admin";
    accessToken?: string;
    refreshToken?: string;
    sessionId?: string;
    sessionToken?: string;
    accessTokenExpires?: number | null;
    error?: string;
  }

  interface Session {
    user: {
      id: string;
      plan: "free" | "pro" | "enterprise";
      role?: "user" | "admin";
    } & DefaultSession["user"];
    accessToken?: string;
    refreshToken?: string;
    sessionId?: string;
    sessionToken?: string;
    accessTokenExpires?: number | null;
    error?: string;
  }
}
