"use client";

import Link from "next/link";
import { Check } from "lucide-react";

const FEATURES = ["무제한 리포트 생성", "Event Study 분석 도구", "Excel 데이터 내보내기", "모든 상장사 데이터 접근"];

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-[#0f172a] py-20 px-4 text-white">
      <div className="mx-auto max-w-5xl text-center">
        <h1 className="text-4xl font-bold">단순하고 투명한 요금제</h1>
        <p className="mt-2 text-slate-400">초기 베타 기간 동안 모든 기능을 무료로 체험하세요.</p>
        <div className="mt-12 mx-auto w-full max-w-sm rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl backdrop-blur-sm relative">
          <div className="absolute top-0 right-0 rounded-bl-xl bg-blue-500 px-3 py-1 text-xs font-bold">BETA</div>
          <h3 className="text-xl font-bold">Pro Access</h3>
          <p className="mt-1 text-sm text-slate-400">모든 기능 · 실시간 업데이트</p>
          <div className="mt-6 text-4xl font-bold">
            $0 <span className="text-lg font-normal text-slate-500">/ mo</span>
          </div>
          <ul className="mt-8 space-y-3 text-left text-slate-300">
            {FEATURES.map((feat) => (
              <li key={feat} className="flex items-center gap-3">
                <span className="rounded-full bg-blue-500/20 p-1 text-blue-400">
                  <Check size={14} />
                </span>
                {feat}
              </li>
            ))}
          </ul>
          <Link href="/auth/signup">
            <button className="mt-8 w-full rounded-xl bg-white py-3 font-bold text-slate-900 transition hover:bg-gray-100">
              무료로 시작하기
            </button>
          </Link>
        </div>
      </div>
    </div>
  );
}
