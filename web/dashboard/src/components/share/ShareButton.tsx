"use client";

import { useState } from "react";
import { Share2 } from "lucide-react";
import fetchWithAuth from "@/lib/fetchWithAuth";
import { toast } from "@/store/toastStore";
import classNames from "classnames";

interface ShareButtonProps {
    resourceType: "chat_session" | "report";
    resourceId: string;
    title?: string;
    className?: string;
}

export function ShareButton({ resourceType, resourceId, title, className }: ShareButtonProps) {
    const [isLoading, setIsLoading] = useState(false);

    const handleShare = async () => {
        setIsLoading(true);
        try {
            const response = await fetchWithAuth("/api/v1/share/create", {
                method: "POST",
                body: JSON.stringify({
                    resource_type: resourceType,
                    resource_id: resourceId,
                    title,
                }),
            });

            if (!response.ok) {
                throw new Error("Failed to create share link");
            }

            const data = await response.json();

            // Copy to clipboard
            await navigator.clipboard.writeText(data.url);

            toast.show({
                intent: "success",
                title: "링크가 복사되었습니다",
                message: "이제 누구에게나 공유할 수 있습니다!",
            });
        } catch (error) {
            console.error("Share failed:", error);
            toast.show({
                intent: "error",
                title: "공유 실패",
                message: "잠시 후 다시 시도해 주세요.",
            });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <button
            type="button"
            onClick={handleShare}
            disabled={isLoading}
            className={classNames(
                "inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                "bg-primary/10 text-primary hover:bg-primary/20",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                className
            )}
            title="공유 링크 복사"
        >
            <Share2 className="h-4 w-4" />
            <span>{isLoading ? "생성 중..." : "공유"}</span>
        </button>
    );
}
