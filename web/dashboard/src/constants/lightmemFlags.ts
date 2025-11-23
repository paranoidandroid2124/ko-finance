import type { PlanMemoryFlags } from "@/store/planStore";

export type LightMemFlagKey = keyof PlanMemoryFlags;

export type LightMemFlagOption = {
  key: LightMemFlagKey;
  label: string;
  helper: string;
};

export const LIGHTMEM_FLAG_OPTIONS: LightMemFlagOption[] = [
  {
    key: "chat",
    label: "Chat 세션 메모리",
    helper: "Chatbot 대화에서 장기 기억을 활성화해 연속적인 질의응답을 지원합니다.",
  },
];
