"use client";

import { ArrowUpRight, AlertTriangle, FileText, ShieldCheck } from "lucide-react";
import { type EvidenceLink, type FiscalAlignmentInsight, type RestatementHighlight } from "@/hooks/useCompanySnapshot";
import { interpretPercentile } from "@/lib/insightTemplates";

const numberFormatter = new Intl.NumberFormat("ko-KR", {
  maximumFractionDigits: 1,
  notation: "compact",
});

type RestatementRadarCardProps = {
  highlights: RestatementHighlight[];
};

type EvidenceBundleCardProps = {
  links: EvidenceLink[];
};

type FiscalAlignmentCardProps = {
  insight: FiscalAlignmentInsight | null | undefined;
};

const formatValue = (value?: number | null, unit?: string | null) => {
  if (value == null) {
    return "—";
  }
  const formatted = numberFormatter.format(value);
  return unit ? `${formatted} ${unit}` : formatted;
};

export function RestatementRadarCard({ highlights }: RestatementRadarCardProps) {
  if (!highlights.length) {
    return (
      <section className="rounded-2xl border border-dashed border-border-light/80 bg-background-cardLight/70 p-4 text-sm text-text-secondaryLight dark:border-border-dark/80 dark:bg-background-cardDark/40 dark:text-text-secondaryDark">
        최근 6개월 내 정정 공시에서 큰 수치 변화가 발견되지 않았습니다.
      </section>
    );
  }

  const relativeMessage = interpretPercentile(
    highlights[0]?.frequencyPercentile ?? null,
    "섹터/시총 그룹 기준 정정 빈도",
  );

  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">Restatement Radar</p>
          <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">정정 공시 영향</h3>
          {relativeMessage.message ? (
            <p className="mt-1 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">{relativeMessage.message}</p>
          ) : null}
        </div>
        <AlertTriangle className="h-5 w-5 text-amber-500" aria-hidden />
      </header>
      <ul className="space-y-3">
        {highlights.map((entry) => (
          <li key={entry.receiptNo} className="rounded-xl border border-border-light/70 px-3 py-3 text-sm dark:border-border-dark/60">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{entry.metricLabel ?? entry.metricCode ?? "지표"}</p>
                <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{entry.title ?? entry.reportName ?? "정정 공시"}</p>
              </div>
              {typeof entry.deltaPercent === "number" ? (
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                    entry.deltaPercent >= 0 ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300" : "bg-rose-500/15 text-rose-600 dark:text-rose-300"
                  }`}
                >
                  {entry.deltaPercent > 0 ? "+" : ""}
                  {entry.deltaPercent.toFixed(1)}%
                </span>
              ) : null}
            </div>
            <dl className="mt-2 grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-text-secondaryLight dark:text-text-secondaryDark">정정 전</dt>
                <dd className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{formatValue(entry.previousValue)}</dd>
              </div>
              <div>
                <dt className="text-text-secondaryLight dark:text-text-secondaryDark">정정 후</dt>
                <dd className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{formatValue(entry.currentValue)}</dd>
              </div>
            </dl>
            {entry.viewerUrl ? (
              <a
                href={entry.viewerUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
              >
                DART 원문 보기
                <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function EvidenceBundleCard({ links }: EvidenceBundleCardProps) {
  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">Evidence Bundle</p>
          <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">근거 링크</h3>
        </div>
        <FileText className="h-5 w-5 text-text-secondaryLight dark:text-text-secondaryDark" aria-hidden />
      </header>
      {links.length ? (
        <div className="space-y-2 text-xs">
          {links.slice(0, 6).map((link) => (
            <div key={`${link.metricCode}-${link.referenceNo}`} className="rounded-xl border border-border-light/70 px-3 py-2 dark:border-border-dark/60">
              <div className="flex items-center justify-between gap-2 text-sm">
                <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{link.metricLabel}</p>
                <span className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{link.periodLabel}</span>
              </div>
              <p className="text-[11px] uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">{link.statementLabel}</p>
              <div className="mt-1 flex items-center justify-between text-sm">
                <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{formatValue(link.value, link.unit)}</span>
                <a
                  href={link.viewerUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-full border border-border-light/60 px-2 py-0.5 text-[11px] text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark/60"
                >
                  원문
                  <ArrowUpRight className="h-3 w-3" aria-hidden />
                </a>
              </div>
            </div>
          ))}
          {links.length > 6 ? (
            <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">+{links.length - 6}개의 추가 근거</p>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">연결된 근거 링크가 아직 없습니다.</p>
      )}
    </section>
  );
}

export function FiscalAlignmentCard({ insight }: FiscalAlignmentCardProps) {
  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">Fiscal Alignment</p>
          <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">회계 정렬 상태</h3>
        </div>
        <ShieldCheck
          className={`h-5 w-5 ${
            insight?.alignmentStatus === "good"
              ? "text-emerald-500"
              : insight?.alignmentStatus === "warning"
                ? "text-amber-500"
                : "text-text-secondaryLight dark:text-text-secondaryDark"
          }`}
          aria-hidden
        />
      </header>
      {insight ? (
        <div className="space-y-3 text-sm">
          <dl className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-text-secondaryLight dark:text-text-secondaryDark">최근 연간</dt>
              <dd className="mt-0.5 font-semibold text-text-primaryLight dark:text-text-primaryDark">{insight.latestAnnualPeriod ?? "정보 없음"}</dd>
            </div>
            <div>
              <dt className="text-text-secondaryLight dark:text-text-secondaryDark">최근 분기</dt>
              <dd className="mt-0.5 font-semibold text-text-primaryLight dark:text-text-primaryDark">{insight.latestQuarterPeriod ?? "정보 없음"}</dd>
            </div>
          </dl>
          <div className="rounded-xl border border-border-light/70 p-3 text-sm dark:border-border-dark/60">
            <p className="text-xs uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">Seasonal YoY</p>
            <p className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
              {typeof insight.yoyDeltaPercent === "number" ? `${insight.yoyDeltaPercent > 0 ? "+" : ""}${insight.yoyDeltaPercent.toFixed(1)}%` : "계산 불가"}
            </p>
          </div>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            TTM 커버리지: <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{insight.ttmQuarterCoverage}</span> 분기
          </p>
          {insight.notes ? <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">{insight.notes}</p> : null}
        </div>
      ) : (
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">정렬 상태를 평가할 데이터가 부족합니다.</p>
      )}
    </section>
  );
}
