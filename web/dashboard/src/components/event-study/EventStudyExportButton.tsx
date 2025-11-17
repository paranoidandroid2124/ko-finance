"use client";

import clsx from "clsx";
import { FileDown, Loader2 } from "lucide-react";
import { useCallback, useState } from "react";
import { useSession } from "next-auth/react";

import {
  exportEventStudyReport,
  type EventStudyExportParams,
  type EventStudyExportResponse,
} from "@/hooks/useEventStudy";
import { useToastStore } from "@/store/toastStore";

type ButtonVariant = "primary" | "secondary";

const VARIANT_STYLES: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-white border border-primary hover:bg-primary/90 dark:bg-primary.dark dark:border-primary.dark dark:hover:bg-primary.dark/80",
  secondary:
    "border border-border-light text-text-primaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-primaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark",
};

const SIZE_STYLES: Record<"sm" | "md", string> = {
  sm: "px-3 py-2 text-xs",
  md: "px-4 py-2 text-sm",
};

type EventStudyExportButtonProps = {
  buildParams: () => EventStudyExportParams;
  className?: string;
  variant?: ButtonVariant;
  size?: "sm" | "md";
  disabled?: boolean;
  children?: React.ReactNode;
};

export function EventStudyExportButton({
  buildParams,
  className,
  variant = "primary",
  size = "md",
  disabled = false,
  children,
}: EventStudyExportButtonProps) {
  const showToast = useToastStore((state) => state.show);
  const { data: session } = useSession();
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = useCallback(async () => {
    if (disabled || isExporting) {
      return;
    }
    let exportResult: EventStudyExportResponse | undefined;
    try {
      setIsExporting(true);
      const params = buildParams();
      exportResult = await exportEventStudyReport({
        ...params,
        requestedBy: params.requestedBy ?? session?.user?.email ?? params.requestedBy,
      });
      const downloadUrl = exportResult.pdfUrl ?? exportResult.packageUrl ?? undefined;
      showToast({
        intent: "success",
        title: "PDF 내보내기 완료",
        message: downloadUrl ? "다운로드 링크를 새 창에서 열 수 있어요." : "오브젝트 스토리지에 리포트를 저장했습니다.",
        actionLabel: downloadUrl ? "열기" : undefined,
        actionHref: downloadUrl,
        duration: downloadUrl ? 7000 : 5000,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "이벤트 스터디 리포트를 내보내지 못했습니다.";
      showToast({
        intent: "error",
        title: "Export 실패",
        message,
        duration: 6000,
      });
    } finally {
      setIsExporting(false);
    }
    return exportResult;
  }, [buildParams, disabled, isExporting, session?.user?.email, showToast]);

  return (
    <button
      type="button"
      className={clsx(
        "inline-flex items-center gap-2 rounded-full font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-60",
        VARIANT_STYLES[variant],
        SIZE_STYLES[size],
        className,
      )}
      onClick={handleExport}
      disabled={disabled || isExporting}
    >
      {isExporting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <FileDown className="h-4 w-4" aria-hidden />}
      <span>{children ?? "PDF 내보내기"}</span>
    </button>
  );
}
