"use client";

import { ChatPageShell } from "@/components/chat/ChatPageShell";
import { useChatController } from "@/hooks/useChatController";

export default function ChatPage() {
  const controller = useChatController();
  return <ChatPageShell controller={controller} />;
}

