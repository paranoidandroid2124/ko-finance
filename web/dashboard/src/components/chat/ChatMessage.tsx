import classNames from "classnames";

export type ChatRole = "user" | "assistant" | "system";

export type ChatMessageProps = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  isGuardrail?: boolean;
};

export function ChatMessageBubble({ role, content, timestamp, isGuardrail }: ChatMessageProps) {
  const isUser = role === "user";
  return (
    <div className={classNames("flex w-full gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/20 text-sm font-semibold text-primary">
          AI
        </div>
      )}
      <div
        className={classNames(
          "max-w-xl rounded-2xl px-4 py-3 text-sm shadow-card transition-colors",
          isUser
            ? "bg-primary text-white"
            : "bg-background-cardLight text-text-primaryLight dark:bg-background-cardDark dark:text-text-primaryDark"
        )}
      >
        <p className="whitespace-pre-wrap leading-relaxed">
          {content}
          {isGuardrail && (
            <span className="mt-2 block text-xs text-accent-warning">
              guardrail 경고가 감지되어 안전 메시지로 대체되었습니다.
            </span>
          )}
        </p>
        <p
          className={classNames(
            "mt-2 text-[11px]",
            isUser ? "text-white/70" : "text-text-secondaryLight dark:text-text-secondaryDark"
          )}
        >
          {timestamp}
        </p>
      </div>
    </div>
  );
}

