import { useMutation } from "@tanstack/react-query";

import fetchWithAuth from "@/lib/fetchWithAuth";
import { toast } from "@/store/toastStore";
import { useReportStore } from "@/stores/useReportStore";
import type { ReportSource } from "@/stores/useReportStore";

type GenerateReportParams = {
  ticker: string;
};

type GenerateReportResponse = {
  reportId?: string | null;
  ticker: string;
  content: string;
  sources: ReportSource[];
  charts?: Record<string, unknown> | null;
};

const fetchReportAPI = async ({ ticker }: GenerateReportParams): Promise<GenerateReportResponse> => {
  const response = await fetchWithAuth("/api/v1/report/generate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ticker }),
  });

  if (!response.ok) {
    let detail = "Failed to generate report";
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") {
        detail = payload.detail;
      }
    } catch (error) {
      // ignore
    }
    throw new Error(detail);
  }

  return response.json();
};

export const useGenerateReport = () => {
  const { setContent, setGenerating, openPanel, setSources, setTicker, setReportId, setCharts } = useReportStore(
    (state) => ({
      setContent: state.setContent,
      setGenerating: state.setGenerating,
      openPanel: state.openPanel,
      setSources: state.setSources,
      setTicker: state.setTicker,
      setReportId: state.setReportId,
      setCharts: state.setCharts,
    })
  );

  return useMutation<GenerateReportResponse, Error, GenerateReportParams>({
    mutationFn: fetchReportAPI,
    onMutate: (variables) => {
      setGenerating(true);
      setContent("");
      setSources([]);
      setTicker(variables.ticker);
      setReportId(undefined);
      setCharts(null);
      openPanel();
      return variables;
    },
    onSuccess: (response, variables) => {
      setContent(response.content);
      setGenerating(false);
      setSources(response.sources ?? []);
      setTicker(response.ticker);
      setReportId(response.reportId ?? undefined);
      setCharts(response.charts ?? null);
      toast.show({
        intent: "success",
        title: "투자 메모가 준비되었습니다.",
        message: `${variables.ticker.toUpperCase()} 리포트 생성을 완료했습니다.`,
      });
    },
    onError: (error, variables) => {
      setGenerating(false);
      toast.show({
        intent: "error",
        title: "리포트 생성 실패",
        message: error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.",
      });
      if (variables?.ticker) {
        console.error("Report generation failed for", variables.ticker, error);
      }
    },
  });
};
