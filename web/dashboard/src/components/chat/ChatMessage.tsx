import classNames from "classnames";
import type { ChatMessageMeta, ChatRole } from "@/store/chatStore";

export type ChatMessageProps = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  meta?: ChatMessageMeta;
  isGuardrail?: boolean;
  onRetry?: () => void;
};

const statusLabel: Record<NonNullable<ChatMessageMeta["status"]>, string> = {
  pending: "답변 준비 중",
  streaming: "전송 중",
  ready: "완료",
  error: "실패",
  blocked: "차단됨"
};

export function ChatMessageBubble({ role, content, timestamp, meta, isGuardrail, onRetry }: ChatMessageProps) {
  const isUser = role === "user";
  const status = meta?.status;
  const showStatusBadge = !isUser && status && status !== "ready";
  const errorMessage =
    typeof meta?.errorMessage === "string" && meta.errorMessage.length > 0
      ? meta.errorMessage
      : "답변을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.";
  const canRetry = Boolean(meta?.retryable && onRetry);

  return (
    <div className={classNames("group flex w-full gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/20 text-sm font-semibold text-primary transition-motion-fast motion-safe:group-hover:-translate-y-1">
          AI
        </div>
      )}
      <div
        className={classNames(
          "max-w-xl rounded-2xl px-4 py-3 text-sm shadow-card transition-colors transition-motion-medium motion-safe:hover:-translate-y-1 motion-safe:group-hover:-translate-y-1",
          isUser
            ? "bg-primary text-white"
            : "bg-background-cardLight text-text-primaryLight dark:bg-background-cardDark dark:text-text-primaryDark"
        )}
      >
        <div className="flex items-start gap-2">
          <p className="flex-1 whitespace-pre-wrap leading-relaxed">
            {content}
            {isGuardrail && (
              <span className="mt-2 block text-xs text-accent-warning">
                guardrail 경고가 감지되어 안전 메시지로 대체되었습니다.
              </span>
            )}
          </p>
          {showStatusBadge && status && (
            <span className="shrink-0 rounded-full bg-border-light px-2 py-0.5 text-[10px] font-semibold uppercase text-text-secondaryLight dark:bg-border-dark dark:text-text-secondaryDark">
              {statusLabel[status] ?? status}
            </span>
          )}
        </div>
        {!isUser && status && (status === "error" || status === "blocked") && (
          <div className="mt-3 space-y-2 rounded-lg border border-accent-negative/40 bg-accent-negative/10 p-3 text-xs text-accent-negative">
            <p>{errorMessage}</p>
            {canRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="rounded-md border border-accent-negative/60 px-3 py-1 text-[11px] font-semibold text-accent-negative transition-colors transition-motion-fast hover:border-accent-negative hover:bg-accent-negative/20 motion-safe:active:translate-y-[1px]"
              >
                다시 시도
              </button>
            )}
          </div>
        )}
        <p
          className={classNames(
            "mt-3 text-[11px]",
            isUser ? "text-white/70" : "text-text-secondaryLight dark:text-text-secondaryDark"
          )}
        >
          {timestamp}
        </p>
      </div>
    </div>
  );
}
