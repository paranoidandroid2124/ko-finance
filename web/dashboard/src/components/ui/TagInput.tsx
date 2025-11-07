import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import clsx from "clsx";
import { X } from "lucide-react";

type TagInputProps = {
  values: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  suggestions?: string[];
  "aria-label"?: string;
  id?: string;
  normalize?: (value: string) => string;
};

export function TagInput({
  values,
  onChange,
  placeholder = "",
  suggestions,
  id,
  "aria-label": ariaLabel,
  normalize,
}: TagInputProps) {
  const [draft, setDraft] = useState("");

  const normalizeValue = useMemo(
    () => (value: string) => {
      const trimmed = value.trim();
      if (!trimmed) {
        return "";
      }
      return normalize ? normalize(trimmed) : trimmed.toUpperCase();
    },
    [normalize],
  );

  const normalizedValues = useMemo(() => {
    return values
      .map((value) => normalizeValue(value))
      .filter((value) => value.length > 0);
  }, [values, normalizeValue]);

  const pendingSuggestions = useMemo(() => {
    if (!suggestions || suggestions.length === 0) {
      return [];
    }
    const needle = draft.trim().toLowerCase();
    const existing = new Set(normalizedValues.map((value) => value.toLowerCase()));
    return suggestions
      .filter((candidate) => {
        const normalizedCandidate = normalizeValue(candidate);
        if (!normalizedCandidate || existing.has(normalizedCandidate.toLowerCase())) {
          return false;
        }
        if (!needle) {
          return true;
        }
        return normalizedCandidate.toLowerCase().includes(needle);
      })
      .map((candidate) => normalizeValue(candidate))
      .slice(0, 8);
  }, [draft, normalizedValues, suggestions, normalizeValue]);

  const emitChange = (nextValues: string[]) => {
    const sanitized = Array.from(
      new Set(
        nextValues
          .map((value) => normalizeValue(value))
          .filter((value) => value.length > 0),
      ),
    );
    onChange(sanitized);
  };

  const handleDraftToken = () => {
    const trimmed = draft.trim();
    if (!trimmed) {
      return;
    }
    emitChange([...normalizedValues, trimmed]);
    setDraft("");
  };

  const handleRemove = (token: string) => {
    emitChange(normalizedValues.filter((value) => value !== token));
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (event) => {
    if (event.key === "Enter" || event.key === "Tab" || event.key === ",") {
      event.preventDefault();
      handleDraftToken();
      return;
    }
    if (event.key === "Backspace" && draft.length === 0 && normalizedValues.length > 0) {
      event.preventDefault();
      const next = [...normalizedValues];
      next.pop();
      emitChange(next);
    }
  };

  return (
    <div className="space-y-2">
      <div
        className={clsx(
          "flex min-h-[2.75rem] flex-wrap items-center gap-1 rounded-lg border border-border-light bg-background-light px-3 py-1.5 transition-colors focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/40 dark:border-border-dark dark:bg-background-dark",
        )}
      >
        <AnimatePresence initial={false}>
          {normalizedValues.map((token) => (
            <motion.span
              key={token}
              layout
              initial={{ scale: 0.85, opacity: 0, y: -6 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.75, opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: [0.22, 0.61, 0.36, 1] }}
              className="group flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-primary transition-colors dark:bg-primary.dark/15 dark:text-primary.dark"
            >
              {token}
              <motion.button
                type="button"
                onClick={() => handleRemove(token)}
                whileTap={{ scale: 0.85 }}
                className="inline-flex h-4 w-4 items-center justify-center rounded-full text-primary/70 transition-all hover:scale-110 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 dark:text-primary.dark/70 dark:hover:text-primary.dark"
              >
              <X className="h-3.5 w-3.5" aria-hidden />
              <span className="sr-only">{token} 제거</span>
            </motion.button>
          </motion.span>
        ))}
        </AnimatePresence>
        <input
          id={id}
          aria-label={ariaLabel}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleDraftToken}
          placeholder={placeholder}
          className="flex-1 min-w-[6rem] bg-transparent text-sm text-text-primaryLight placeholder:text-text-secondaryLight focus:outline-none dark:text-text-primaryDark dark:placeholder:text-text-secondaryDark"
        />
      </div>
      {pendingSuggestions.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">추천:</span>
          {pendingSuggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => emitChange([...normalizedValues, suggestion])}
              className="rounded-full border border-border-light/70 px-2 py-0.5 transition-colors hover:border-primary/50 hover:bg-primary/10 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:border-border-dark/70 dark:hover:border-primary.dark/50 dark:hover:bg-primary.dark/10 dark:hover:text-primary.dark"
            >
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
