"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, Search, Sparkles, TrendingUp } from "lucide-react";

const SUGGESTIONS = [
    "삼성전자 3분기 실적 요약해줘",
    "테슬라 vs BYD 경쟁력 비교",
    "최근 HBM 관련주 동향 알려줘",
];

export function InteractiveHero() {
    const [input, setInput] = useState("");
    const router = useRouter();
    const [isFocused, setIsFocused] = useState(false);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim()) return;
        router.push(`/dashboard?guest=1&prefill=${encodeURIComponent(input.trim())}`);
    };

    return (
        <div className="relative w-full max-w-3xl mx-auto">
            {/* Main Input Card */}
            <div className="relative rounded-[32px] border border-border-subtle bg-surface-muted/90 p-2 shadow-card backdrop-blur-xl transition-all duration-300 hover:shadow-elevation-2">
                <form onSubmit={handleSubmit} className="relative flex items-center">
                    <div className="pointer-events-none absolute left-6 flex items-center justify-center text-slate-400">
                        <Search className="h-6 w-6" />
                    </div>
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onFocus={() => setIsFocused(true)}
                        onBlur={() => setIsFocused(false)}
                        placeholder="궁금한 기업이나 시장 이슈를 물어보세요..."
                        className="h-16 w-full rounded-[24px] bg-transparent pl-16 pr-16 text-lg font-medium text-white placeholder:text-slate-400 focus:bg-white/5 focus:outline-none"
                        autoFocus
                    />
                    <div className="absolute right-3">
                        <button
                            type="submit"
                            disabled={!input.trim()}
                            className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-white transition-all hover:bg-primary-hover disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed"
                            aria-label="검색"
                        >
                            <ArrowRight className="h-5 w-5" />
                        </button>
                    </div>
                </form>
            </div>

            {/* Suggestions / Tags */}
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="mt-6 flex flex-wrap items-center justify-center gap-3"
            >
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    <TrendingUp className="h-3.5 w-3.5" />
                    Trending
                </div>
                {SUGGESTIONS.map((suggestion, idx) => (
                    <button
                        key={idx}
                        onClick={() => {
                            setInput(suggestion);
                            router.push(`/dashboard?guest=1&prefill=${encodeURIComponent(suggestion)}`);
                        }}
                        className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300 transition-colors hover:border-primary/50 hover:bg-primary/10 hover:text-white"
                    >
                        {suggestion}
                    </button>
                ))}
            </motion.div>

            {/* Decorative Elements */}
            <div className="pointer-events-none absolute -top-20 -left-20 h-64 w-64 rounded-full bg-blue-500/10 blur-[80px]" />
            <div className="pointer-events-none absolute -bottom-20 -right-20 h-64 w-64 rounded-full bg-purple-500/10 blur-[80px]" />
        </div>
    );
}
