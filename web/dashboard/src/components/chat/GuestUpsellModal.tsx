"use client";

import Link from "next/link";
import { X } from "lucide-react";

type GuestUpsellModalProps = {
  open: boolean;
  onClose: () => void;
};

export function GuestUpsellModal({ open, onClose }: GuestUpsellModalProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-lg rounded-3xl border border-white/10 bg-gradient-to-br from-[#0b1224] to-[#0f1c2f] p-6 shadow-[0_25px_120px_rgba(5,13,34,0.65)]">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.25em] text-blue-200">Guest Trial</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Nuvien 체험을 계속 하려면 가입해 주세요.</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/10 bg-white/5 p-2 text-slate-200 transition hover:border-white/30 hover:text-white"
            aria-label="모달 닫기"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-slate-200">
          방금 본 분석은 저장되지 않고, 세 번의 질문 기회만 제공돼요. 네 번째 질문부터는 가입 후 이용할 수 있어요.
          Google 계정으로 10초면 끝납니다.
        </p>
        <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200">
          <p className="font-semibold text-white">여기서 동작:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-300">
            <li>비로그인 사용자는 질문 3회만 즉시 체험 가능</li>
            <li>리포트 저장·리스크 하이라이트는 가입 후 이어서 제공</li>
            <li>Google 계정으로 10초 만에 가입하고 바로 이어서 질문</li>
          </ul>
        </div>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-full border border-white/20 px-4 py-3 text-sm font-semibold text-white/80 transition hover:border-white/40 hover:text-white sm:w-auto"
          >
            나중에 할게요
          </button>
          <Link
            href="/auth/signup?from=guest_chat"
            className="w-full rounded-full bg-white px-5 py-3 text-center text-sm font-semibold text-slate-900 shadow-lg shadow-white/30 transition hover:scale-[1.01] sm:w-auto"
          >
            Google로 10초 만에 가입하기
          </Link>
        </div>
      </div>
    </div>
  );
}

