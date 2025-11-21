"use client";

import Link from "next/link";

type AccountSecuritySettingsPanelProps = {
  onClose?: () => void;
};

export function AccountSecuritySettingsPanel({ onClose }: AccountSecuritySettingsPanelProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">계정 / 보안</h3>
          <p className="text-sm text-slate-400">프로필, 플랜, 데이터 관리 옵션</p>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 transition hover:border-white/30 hover:text-white"
          >
            닫기
          </button>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-lg">
          <p className="text-sm font-semibold text-white">프로필</p>
          <div className="space-y-1 text-sm text-slate-300">
            <p>이름: 계정 프로필 업데이트는 준비 중입니다.</p>
            <p>이메일: 로그인 계정 이메일을 사용합니다.</p>
          </div>
        </div>

        <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-lg">
          <p className="text-sm font-semibold text-white">플랜 요약</p>
          <div className="text-sm text-slate-300">
            <p>현재 플랜: 대시보드 상단 요약을 참고하세요.</p>
            <Link
              href="/payments"
              className="mt-2 inline-flex items-center gap-2 rounded-lg bg-blue-500 px-3 py-2 text-xs font-semibold text-white shadow hover:bg-blue-400"
            >
              결제 관리로 이동
            </Link>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ActionCard
          title="비밀번호 변경"
          description="비밀번호 변경은 로그인 공급사(Supabase/SSO) 설정에서 진행하세요."
          disabled
        />
        <ActionCard
          title="데이터 내보내기"
          description="대화/프로필 데이터를 다운로드하는 기능은 준비 중입니다."
          disabled
        />
        <ActionCard
          title="계정 삭제"
          description="계정 및 데이터를 삭제하는 기능은 백엔드 API 확인 후 활성화됩니다."
          disabled
          tone="danger"
        />
      </div>
    </div>
  );
}

function ActionCard({
  title,
  description,
  disabled,
  tone = "neutral",
}: {
  title: string;
  description: string;
  disabled?: boolean;
  tone?: "neutral" | "danger";
}) {
  return (
    <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-lg">
      <div>
        <p className="text-sm font-semibold text-white">{title}</p>
        <p className="text-xs text-slate-400">{description}</p>
      </div>
      <button
        type="button"
        disabled={disabled}
        className={`rounded-lg px-3 py-2 text-xs font-semibold transition ${
          tone === "danger"
            ? "bg-rose-500/70 text-white hover:bg-rose-500"
            : "bg-slate-700/70 text-white hover:bg-slate-700"
        } disabled:cursor-not-allowed disabled:opacity-40`}
      >
        준비 중
      </button>
    </div>
  );
}
