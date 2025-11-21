import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATH_PREFIXES = ["/auth", "/public", "/pricing", "/chat", "/dashboard"];

const isPublicPath = (pathname: string) => {
  if (pathname === "/" || pathname === "") {
    return true;
  }
  return PUBLIC_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
};

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }
  // Supabase 세션은 클라이언트에서 관리하므로, 서버 미들웨어에서는 우선 통과시킵니다.
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
