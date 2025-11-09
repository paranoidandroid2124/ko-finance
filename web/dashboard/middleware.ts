import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

const PROTECTED_PREFIXES = ["/app", "/dashboard"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const requiresAuth = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  if (!requiresAuth) {
    return NextResponse.next();
  }

  const token = await getToken({ req: request, secret: process.env.AUTH_SECRET });
  if (!token) {
    const loginUrl = new URL("/login", request.nextUrl.origin);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
