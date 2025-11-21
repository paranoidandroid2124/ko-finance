"use client";

import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Sparkles } from "lucide-react";

import { LightMemSettingsPanel } from "./LightMemSettingsPanel";
import { ProactiveSettingsPanel } from "./ProactiveSettingsPanel";
import { GeneralSettingsPanel } from "./GeneralSettingsPanel";
import { AccountSecuritySettingsPanel } from "./AccountSecuritySettingsPanel";
import { useSettingsModalStore } from "@/store/settingsModalStore";
import type { SettingsSection } from "@/store/settingsModalStore";

const sections: Array<{ id: SettingsSection; label: string; description: string }> = [
  { id: "account", label: "계정/보안", description: "프로필·플랜·데이터" },
  { id: "lightmem", label: "LightMem 제어", description: "관심 태그와 개인화 설정" },
  { id: "proactive", label: "프로액티브 인사이트", description: "먼저 알려주는 알림 채널" },
  { id: "general", label: "일반", description: "테마·언어 설정" },
];

export function SettingsModal() {
  const { open, activeSection, setActiveSection, closeModal } = useSettingsModalStore();

  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeModal();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, closeModal]);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="relative flex h-[80vh] w-[960px] max-w-[95vw] overflow-hidden rounded-3xl border border-white/10 bg-[#0c111d]/90 shadow-[0_24px_120px_rgba(0,0,0,0.45)]"
            initial={{ scale: 0.96, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={{ type: "spring", stiffness: 180, damping: 24 }}
          >
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute -left-24 -top-32 h-64 w-64 rounded-full bg-blue-500/10 blur-[120px]" />
              <div className="absolute -right-20 bottom-[-120px] h-80 w-80 rounded-full bg-cyan-400/10 blur-[140px]" />
            </div>
            <aside className="relative z-10 w-56 border-r border-white/10 bg-white/[0.03] p-5">
              <div className="mb-6 flex items-center gap-2 text-sm font-semibold text-white">
                <Sparkles className="h-4 w-4 text-blue-400" />
                Settings
              </div>
              <nav className="space-y-2">
                {sections.map((section) => {
                  const active = activeSection === section.id;
                  return (
                    <button
                      key={section.id}
                      type="button"
                      onClick={() => setActiveSection(section.id)}
                      className={`w-full rounded-xl px-3 py-3 text-left transition ${
                        active
                          ? "bg-white/10 text-white shadow-[0_12px_36px_rgba(88,166,255,0.25)]"
                          : "text-slate-300 hover:bg-white/5"
                      }`}
                    >
                      <p className="text-sm font-semibold">{section.label}</p>
                      <p className="text-[11px] text-slate-400">{section.description}</p>
                    </button>
                  );
                })}
              </nav>
              <div className="mt-6 text-[11px] text-slate-500">
                Esc 를 눌러 닫기 <br />
                설정은 즉시 저장됩니다.
              </div>
            </aside>
            <section className="relative z-10 flex-1 overflow-y-auto p-8">
              {activeSection === "account" ? <AccountSecuritySettingsPanel onClose={closeModal} /> : null}
              {activeSection === "lightmem" ? <LightMemSettingsPanel onClose={closeModal} /> : null}
              {activeSection === "proactive" ? <ProactiveSettingsPanel onClose={closeModal} /> : null}
              {activeSection === "general" ? <GeneralSettingsPanel onClose={closeModal} /> : null}
            </section>
          </motion.div>
          <button
            type="button"
            onClick={closeModal}
            className="absolute inset-0 h-full w-full"
            aria-label="설정 모달 닫기"
          />
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
