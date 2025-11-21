"use client";

import { useEffect, useMemo, useState } from "react";
import { X, PlusCircle } from "lucide-react";

import { fetchWithAuth } from "@/lib/fetchWithAuth";
import { useToastStore } from "@/store/toastStore";

type InterestResponse = {
  interests?: string[];
  enabled?: boolean;
};

type LightMemSettingsPanelProps = {
  onClose?: () => void;
};

export function LightMemSettingsPanel({ onClose }: LightMemSettingsPanelProps) {
  const pushToast = useToastStore((state) => state.show);
  const [interests, setInterests] = useState<string[]>([]);
  const [enabled, setEnabled] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [newTag, setNewTag] = useState<string>("");

  const sortedInterests = useMemo(() => [...interests].sort(), [interests]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetchWithAuth("/api/v1/profile/interest");
        if (!res.ok) {
          throw new Error(`failed ${res.status}`);
        }
        const data = (await res.json()) as InterestResponse;
        if (cancelled) return;
        setInterests(Array.isArray(data.interests) ? data.interests.filter((t) => typeof t === "string") : []);
        setEnabled(data.enabled !== false);
      } catch (error) {
        if (!cancelled) {
          pushToast({
            id: `lightmem/load/${Date.now()}`,
            intent: "error",
            title: "프로필을 불러오지 못했습니다.",
            message: error instanceof Error ? error.message : undefined,
          });
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [pushToast]);

  const updateEnabled = async (next: boolean) => {
    setEnabled(next);
    try {
      await fetchWithAuth("/api/v1/profile/interest", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
    } catch {
      // rollback on failure
      setEnabled(!next);
      pushToast({
        id: `lightmem/toggle/${Date.now()}`,
        intent: "error",
        title: "저장 실패",
        message: "LightMem 설정을 저장하지 못했습니다.",
      });
    }
  };

  const addInterest = async () => {
    const tag = newTag.trim();
    if (!tag) return;
    setSaving(true);
    try {
      const res = await fetchWithAuth("/api/v1/profile/interest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interests: [tag] }),
      });
      if (!res.ok) {
        throw new Error(`failed ${res.status}`);
      }
      setInterests((prev) => Array.from(new Set([...prev, tag])));
      setNewTag("");
    } catch (error) {
      pushToast({
        id: `lightmem/add/${Date.now()}`,
        intent: "error",
        title: "태그를 추가하지 못했습니다.",
        message: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSaving(false);
    }
  };

  const removeInterest = async (tag: string) => {
    setSaving(true);
    try {
      const res = await fetchWithAuth(`/api/v1/profile/interest`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interest: tag }),
      });
      if (!res.ok) {
        throw new Error(`failed ${res.status}`);
      }
      setInterests((prev) => prev.filter((item) => item !== tag));
    } catch (error) {
      pushToast({
        id: `lightmem/remove/${Date.now()}`,
        intent: "error",
        title: "태그를 삭제하지 못했습니다.",
        message: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSaving(false);
    }
  };

  const clearInterests = async () => {
    setSaving(true);
    try {
      const res = await fetchWithAuth("/api/v1/profile/interest", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ clear_all: true }),
      });
      if (!res.ok) {
        throw new Error(`failed ${res.status}`);
      }
      setInterests([]);
    } catch (error) {
      pushToast({
        id: `lightmem/clear/${Date.now()}`,
        intent: "error",
        title: "기억 삭제 실패",
        message: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">LightMem 제어</h3>
          <p className="text-sm text-slate-400">대화 기반 관심사 학습과 개인화를 관리합니다.</p>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/10 p-2 text-slate-300 transition hover:border-white/30 hover:text-white"
            aria-label="설정 닫기"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-lg">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-white">LightMem 활성화</p>
            <p className="text-xs text-slate-400">대화 맥락을 학습해 답변을 개인화합니다.</p>
          </div>
          <label className="relative inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              className="peer sr-only"
              checked={enabled}
              disabled={loading || saving}
              onChange={(event) => updateEnabled(event.target.checked)}
            />
            <div className="peer h-6 w-11 rounded-full bg-slate-600 after:absolute after:left-[4px] after:top-[4px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:bg-blue-500 peer-checked:after:translate-x-5 peer-disabled:opacity-60" />
          </label>
        </div>
      </div>

      <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-lg">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-white">나의 관심 프로필</p>
            <p className="text-xs text-slate-400">태그를 삭제하거나 새로 추가할 수 있습니다.</p>
          </div>
          <button
            type="button"
            onClick={clearInterests}
            disabled={saving || interests.length === 0}
            className="text-xs font-semibold text-rose-300 transition hover:text-rose-100 disabled:opacity-50"
          >
            전체 삭제
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {loading ? (
            <span className="text-xs text-slate-400">불러오는 중…</span>
          ) : sortedInterests.length ? (
            sortedInterests.map((tag) => (
              <button
                key={tag}
                type="button"
                disabled={saving}
                onClick={() => removeInterest(tag)}
                className="group inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-slate-100 transition hover:border-white/30 hover:bg-white/10 disabled:opacity-60"
              >
                <span>{tag}</span>
                <X className="h-3 w-3 text-slate-300 transition group-hover:text-white" />
              </button>
            ))
          ) : (
            <span className="text-xs text-slate-500">아직 저장된 관심 태그가 없습니다.</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newTag}
            onChange={(event) => setNewTag(event.target.value)}
            placeholder="예: 삼성전자, 2차전지, 미국 금리"
            className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-blue-400 focus:outline-none"
          />
          <button
            type="button"
            onClick={addInterest}
            disabled={saving || !newTag.trim()}
            className="inline-flex items-center gap-1 rounded-lg bg-blue-500 px-3 py-2 text-sm font-semibold text-white shadow transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <PlusCircle className="h-4 w-4" />
            추가
          </button>
        </div>
      </div>
    </div>
  );
}
