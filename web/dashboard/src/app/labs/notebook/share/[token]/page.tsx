"use client";

import { FormEvent, useEffect, useState } from "react";
import { notFound } from "next/navigation";

import type { NotebookShareAccessResponse } from "@/lib/notebookApi";
import { NotebookApiError, resolveNotebookShare } from "@/lib/notebookApi";

type SharePageProps = {
  params: { token: string };
};

export default function NotebookSharePublicPage({ params }: SharePageProps) {
  if (process.env.NEXT_PUBLIC_ENABLE_LABS !== "true") {
    notFound();
  }

  const [password, setPassword] = useState("");
  const [access, setAccess] = useState<NotebookShareAccessResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requiresPassword, setRequiresPassword] = useState(false);

  const resolveShareLink = async (passwordOverride?: string) => {
    setLoading(true);
    try {
      const result = await resolveNotebookShare({ token: params.token, password: passwordOverride });
      setAccess(result);
      setError(null);
      setRequiresPassword(false);
    } catch (err) {
      if (err instanceof NotebookApiError && err.code === "notebook.share.password_required") {
        setRequiresPassword(true);
        setError("비밀번호가 필요합니다.");
      } else {
        setError(err instanceof NotebookApiError ? err.message : "공유 링크를 불러오지 못했습니다.");
      }
      setAccess(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    resolveShareLink();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.token]);

  const handlePasswordSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await resolveShareLink(password);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 px-4 py-10 text-white">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="space-y-2 text-center">
          <p className="text-xs uppercase tracking-[0.2em] text-emerald-300">K-Finance Research Notebook</p>
          <h1 className="text-3xl font-semibold">{access?.notebook.title ?? "공유 노트북"}</h1>
          {access?.notebook.summary ? <p className="text-sm text-slate-300">{access.notebook.summary}</p> : null}
        </header>
        {requiresPassword ? (
          <form onSubmit={handlePasswordSubmit} className="mx-auto flex max-w-md flex-col gap-3 rounded-2xl border border-slate-700/70 bg-slate-900/70 p-4 shadow-lg">
            <label className="text-sm text-slate-200">
              공유 비밀번호
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white focus:border-emerald-400 focus:outline-none"
                placeholder="비밀번호를 입력하세요"
              />
            </label>
            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-black transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "확인 중..." : "열기"}
            </button>
          </form>
        ) : null}
        {error && !requiresPassword ? (
          <div className="rounded-2xl border border-red-400/60 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>
        ) : null}
        {loading && !requiresPassword ? <div className="animate-pulse rounded-2xl border border-slate-800/80 bg-slate-900/60 p-6 text-center text-slate-300">불러오는 중...</div> : null}
        {access ? (
          <section className="space-y-4 rounded-2xl border border-slate-800/60 bg-slate-900/60 p-6 shadow-xl">
            <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-slate-400">
              공유 링크 · 만료 {access.share.expiresAt ? new Date(access.share.expiresAt).toLocaleString("ko-KR") : "제한 없음"}
            </div>
            <div className="flex flex-wrap gap-2">
              {access.notebook.tags.map((tag) => (
                <span key={tag} className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs text-emerald-200">
                  #{tag}
                </span>
              ))}
            </div>
            <div className="space-y-4">
              {access.entries.map((entry) => (
                <article key={entry.id} className="space-y-2 rounded-2xl border border-slate-800/80 bg-slate-950/50 p-4">
                  <p className="text-base font-semibold text-white">{entry.highlight}</p>
                  {entry.annotation ? <p className="whitespace-pre-wrap text-sm text-slate-300">{entry.annotation}</p> : null}
                  <div className="flex flex-wrap gap-2 text-xs text-slate-400">
                    {entry.tags.map((tag) => (
                      <span key={tag} className="rounded-full border border-slate-700 px-2 py-0.5">
                        #{tag}
                      </span>
                    ))}
                  </div>
                  {entry.source?.label || entry.source?.url ? (
                    <div className="text-xs text-slate-500">
                      {entry.source.label ? <span>{entry.source.label}</span> : null}
                      {entry.source.url ? (
                        <a href={entry.source.url} target="_blank" rel="noreferrer" className="ml-2 text-emerald-300 underline">
                          링크 열기
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
