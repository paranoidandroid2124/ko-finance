"use client";

import { AnimatePresence } from "framer-motion";
import { AlertBellTrigger } from "./AlertBellTrigger";
import { AlertBellPanel } from "./AlertBellPanel";
import { useAlertBellController } from "./useAlertBellController";

export function AlertBell() {
  const { containerRef, containerHandlers, triggerProps, panelProps, isOpen } = useAlertBellController();

  return (
    <div
      ref={containerRef}
      data-testid="alert-bell"
      className="relative flex h-10 w-10 items-center justify-center"
      onMouseEnter={containerHandlers.onMouseEnter}
      onMouseLeave={containerHandlers.onMouseLeave}
      onFocusCapture={containerHandlers.onFocusCapture}
      onBlurCapture={containerHandlers.onBlurCapture}
    >
      <AlertBellTrigger {...triggerProps} />
      <AnimatePresence>{isOpen ? <AlertBellPanel {...panelProps} /> : null}</AnimatePresence>
    </div>
  );
}
