"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";
import { Loader2 } from "lucide-react";
import Link from "next/link";

interface SharedMessage {
    id: string;
    role: string;
    content: string;
    meta?: any;
    created_at: string;
}

interface SharedData {
    resource_type: string;
    title: string | null;
    created_at: string;
    view_count: number;
    data: {
        session_id?: string;
        title?: string;
        messages?: SharedMessage[];
    };
}

export default function SharedContentPage() {
    const params = useParams();
    const router = useRouter();
    const token = params.token as string;

    const [data, setData] = useState<SharedData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!token) return;

        const fetchSharedContent = async () => {
            try {
                const response = await fetch(`/api/v1/public/share/${token}`);

                if (!response.ok) {
                    if (response.status === 404) {
                        setError("링크를 찾을 수 없거나 만료되었습니다.");
                    } else {
                        setError("컨텐츠를 불러오는 중 오류가 발생했습니다.");
                    }
                    return;
                }

                const result = await response.json();
                setData(result);
            } catch (err) {
                console.error("Failed to fetch shared content:", err);
                setError("컨텐츠를 불러오는 중 오류가 발생했습니다.");
            } finally {
                setLoading(false);
            }
        };

        fetchSharedContent();
    }, [token]);

    if (loading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-canvas">
                <div className="text-center">
                    <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
                    <p className="mt-4 text-sm text-text-secondary">불러오는 중...</p>
                </div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
                <Card variant="raised" padding="lg" className="max-w-md text-center">
                    <h1 className="text-xl font-bold text-text-primary">링크 오류</h1>
                    <p className="mt-2 text-sm text-text-secondary">
                        {error || "컨텐츠를 찾을 수 없습니다."}
                    </p>
                    <Link
                        href="/"
                        className="mt-6 inline-block rounded-lg bg-primary px-6 py-2 text-sm font-medium text-white hover:bg-primary/90"
                    >
                        홈으로 돌아가기
                    </Link>
                </Card>
            </div>
        );
    }

    const { resource_type, title, data: resourceData } = data;

    return (
        <div className="min-h-screen bg-canvas">
            {/* Top banner */}
            <div className="sticky top-0 z-50 border-b border-border-light bg-background-card/95 backdrop-blur-sm dark:border-border-dark dark:bg-background-cardDark/95">
                <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
                    <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20 text-sm font-bold text-primary">
                            N
                        </div>
                        <div>
                            <p className="text-xs text-text-secondary">이 컨텐츠는 Nuvien에서 생성되었습니다</p>
                        </div>
                    </div>
                    <Link
                        href="/dashboard?guest=1"
                        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 transition-colors"
                    >
                        무료로 시작하기
                    </Link>
                </div>
            </div>

            {/* Content */}
            <div className="mx-auto max-w-4xl px-4 py-8">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-text-primary">
                        {title || resourceData.title || "공유된 대화"}
                    </h1>
                    <p className="mt-1 text-sm text-text-secondary">
                        조회수 {data.view_count}회 · {new Date(data.created_at).toLocaleDateString("ko-KR")}
                    </p>
                </div>

                {resource_type === "chat_session" && resourceData.messages && (
                    <div className="space-y-4">
                        {resourceData.messages.map((message) => (
                            <ChatMessageBubble
                                key={message.id}
                                id={message.id}
                                role={message.role as any}
                                content={message.content}
                                timestamp={new Date(message.created_at).toLocaleString("ko-KR")}
                                meta={message.meta}
                            />
                        ))}
                    </div>
                )}

                {resource_type === "report" && (
                    <Card variant="raised" padding="lg">
                        <p className="text-text-secondary">리포트 공유는 곧 지원될 예정입니다.</p>
                    </Card>
                )}

                {/* CTA Footer */}
                <div className="mt-12 rounded-2xl border border-primary/30 bg-gradient-to-br from-primary/10 to-primary/5 p-8 text-center">
                    <h2 className="text-xl font-bold text-text-primary">
                        이런 분석이 필요하신가요?
                    </h2>
                    <p className="mt-2 text-sm text-text-secondary">
                        Nuvien으로 AI 기반 투자 리서치를 시작하세요
                    </p>
                    <Link
                        href="/dashboard?guest=1"
                        className="mt-6 inline-block rounded-lg bg-primary px-8 py-3 text-sm font-semibold text-white hover:bg-primary/90 transition-colors"
                    >
                        3회 무료 체험 시작
                    </Link>
                </div>
            </div>
        </div>
    );
}
