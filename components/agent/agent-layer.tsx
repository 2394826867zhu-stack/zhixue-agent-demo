"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, FilePlus2, Loader2, Mic, Send, Sparkles, X } from "lucide-react";
import { AgentOrb } from "@/components/agent/agent-orb";
import { Button } from "@/components/ui/button";
import { getTodayCheckIn, streamAgentChat, type CheckIn } from "@/lib/api";
import { cn } from "@/lib/utils";

type AgentMessage = {
  id: string;
  role: "agent" | "user" | "system";
  content: string;
  result?: CheckIn;
};

const SUGGESTIONS = [
  "帮我复习今天这节课",
  "根据错题生成 quiz",
  "整理今天学了什么",
];

const QUICK_ACTIONS = [
  { label: "上传资料", icon: FilePlus2 },
  { label: "语音", icon: Mic },
  { label: "生成 quiz", icon: Sparkles },
  { label: "成绩分析", icon: BarChart3 },
];

function AgentCommandPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesViewportRef = useRef<HTMLDivElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const messageSeqRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const hasMessages = messages.length > 0;

  function refreshAgentSideEffects() {
    queryClient.invalidateQueries({ queryKey: ["agent-today-checkin"] });
    queryClient.invalidateQueries({ queryKey: ["today-tasks"] });
    queryClient.invalidateQueries({ queryKey: ["kps"] });
    queryClient.invalidateQueries({ queryKey: ["kp-stats"] });
    queryClient.invalidateQueries({ queryKey: ["progress-overview"] });
    queryClient.invalidateQueries({ queryKey: ["profile-insights"] });
  }

  const agentMutation = useMutation({
    mutationFn: async ({ content, assistantId }: { content: string; assistantId: string }) =>
      streamAgentChat(content, sessionId, {
        onThinking: (thinking) => {
          setMessages((prev) =>
            prev.map((item) =>
              item.id === assistantId && item.role === "system"
                ? { ...item, content: thinking }
                : item
            )
          );
        },
        onDelta: (delta) => {
          setMessages((prev) =>
            prev.map((item) =>
              item.id === assistantId
                ? { ...item, role: "agent", content: item.role === "system" ? delta : item.content + delta }
                : item
            )
          );
        },
        onDone: (event) => {
          setSessionId(event.session_id);
          refreshAgentSideEffects();
        },
      }),
    onSuccess: () => {
      refreshAgentSideEffects();
    },
    onError: (_error, variables) => {
      setMessages((prev) => [
        ...prev.filter((item) => item.id !== variables.assistantId),
        { id: variables.assistantId, role: "agent", content: "AI 管家暂时没有连接成功，请稍后重试。" },
      ]);
    },
  });

  function submit(text = input) {
    const content = text.trim();
    if (!content || agentMutation.isPending) return;
    messageSeqRef.current += 1;
    const userId = `user-${messageSeqRef.current}`;
    const assistantId = `agent-${messageSeqRef.current}`;
    setInput("");
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content },
      { id: assistantId, role: "system", content: "正在连接 AI 管家..." },
    ]);
    agentMutation.mutate({ content, assistantId });
  }

  useEffect(() => {
    if (!open || messages.length === 0) return;
    window.requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    });
  }, [messages.length, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center px-3 pb-[calc(7.25rem+env(safe-area-inset-bottom))] sm:px-5 md:pb-[18vh]">
      <button
        aria-label="关闭 AI 管家"
        className="absolute inset-0 bg-background/18 backdrop-blur-[2px]"
        onClick={onClose}
      />

      <section className="relative w-full max-w-[calc(100vw-1.5rem)] overflow-visible sm:max-w-3xl">
        <div className="mx-auto mb-2 flex items-center gap-2 overflow-x-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {QUICK_ACTIONS.map(({ label, icon: Icon }) => (
            <button
              key={label}
              type="button"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-primary/18 bg-[linear-gradient(180deg,oklch(1_0_0_/_0.84),oklch(0.965_0.012_180_/_0.68))] text-foreground/62 shadow-[0_8px_24px_oklch(0.64_0.17_170_/_10%),inset_0_1px_0_oklch(1_0_0_/_0.90),inset_0_-1px_0_oklch(0.64_0.17_170_/_0.10)] backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-primary/34 hover:text-foreground"
              title={label}
              aria-label={label}
              onClick={
                label === "上传资料"
                  ? () => fileInputRef.current?.click()
                  : label === "语音"
                  ? () => {
                      const SpeechRecognition =
                        (window as any).SpeechRecognition ||
                        (window as any).webkitSpeechRecognition;
                      if (!SpeechRecognition) {
                        console.error("Speech recognition not supported");
                        return;
                      }
                      const recognition = new SpeechRecognition();
                      recognition.lang = "zh-CN";
                      recognition.continuous = false;
                      recognition.interimResults = false;
                      recognition.onresult = (event: any) => {
                        const transcript = event.results[0][0].transcript;
                        setInput((prev: string) => prev + transcript);
                      };
                      recognition.onerror = (event: any) => {
                        console.error("Speech recognition error", event.error);
                      };
                      recognition.start();
                    }
                  : undefined
              }
            >
              <Icon size={16} />
            </button>
          ))}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,application/pdf"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              const formData = new FormData();
              formData.append("file", file);
              try {
                await fetch("http://localhost:8000/v1/notes/upload/file", {
                  method: "POST",
                  headers: {
                    Authorization: `Bearer ${localStorage.getItem("access_token")}`,
                  },
                  body: formData,
                });
              } catch (err) {
                console.error("Upload failed", err);
              }
              e.target.value = "";
            }}
          />
        </div>

        {!hasMessages && (
        <div className="mx-auto mb-2 flex flex-col gap-2 px-1 sm:flex-row sm:items-center sm:overflow-x-auto sm:[scrollbar-width:none] sm:[&::-webkit-scrollbar]:hidden">
          {SUGGESTIONS.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => submit(item)}
              className="h-8 w-fit shrink-0 rounded-full border border-primary/18 bg-[linear-gradient(180deg,oklch(1_0_0_/_0.84),oklch(0.965_0.012_180_/_0.68))] px-3 text-xs font-medium text-foreground/72 shadow-[0_8px_24px_oklch(0.64_0.17_170_/_8%),inset_0_1px_0_oklch(1_0_0_/_0.90),inset_0_-1px_0_oklch(0.64_0.17_170_/_0.10)] backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-primary/34 hover:text-foreground sm:w-auto"
            >
              {item}
            </button>
          ))}
        </div>
        )}

        {hasMessages && (
          <div
            ref={messagesViewportRef}
            className="relative mx-auto mb-2 max-h-[min(30dvh,14rem)] max-w-2xl space-y-2 overflow-y-auto rounded-[1.4rem] border border-white/60 bg-white/58 p-2 shadow-[0_12px_40px_oklch(0.64_0.17_170_/_12%)] backdrop-blur-xl transition-[max-height,opacity] duration-300 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            {messages.map((message) => (
              <div key={message.id} className={cn("flex", message.role === "user" && "justify-end")}>
                <div
                  className={cn(
                    "max-w-[88%] rounded-[1.15rem] px-3 py-2 text-xs leading-relaxed",
                    message.role === "user"
                      ? "bg-primary/12 text-foreground rounded-br-md"
                      : message.role === "system"
                        ? "border border-primary/14 bg-white/62 text-primary"
                        : "border border-white/65 bg-white/72 text-foreground shadow-sm rounded-bl-md"
                  )}
                >
                  {message.role === "system" && (
                    <span className="mr-2 inline-flex align-middle">
                      <Loader2 size={14} className="animate-spin" />
                    </span>
                  )}
                  {message.content}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}

        <div className="relative overflow-hidden rounded-full border border-primary/34 bg-[oklch(0.995_0.008_180_/_0.88)] p-1.5 shadow-[0_18px_58px_oklch(0.64_0.17_170_/_18%),0_1px_0_oklch(1_0_0_/_86%)_inset,0_0_0_1px_oklch(0.82_0.10_170_/_18%)] backdrop-blur-2xl animate-agent-sheet">
          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(110deg,oklch(1_0_0_/_0.20),transparent_32%,oklch(0.76_0.11_172_/_0.16)_66%,transparent)] animate-agent-panel-flow" />
          <div className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-primary/45 to-transparent" />

          <div className="relative">
            <div className="flex min-h-[64px] items-center gap-2 rounded-full border border-primary/22 bg-white/76 p-2 shadow-[0_0_0_1px_oklch(1_0_0_/_60%)_inset,0_0_34px_oklch(0.64_0.17_170_/_10%)] backdrop-blur-xl transition-[border-color,box-shadow,background-color] duration-300 focus-within:border-primary/48 focus-within:bg-white/86 focus-within:shadow-[0_0_0_1px_oklch(1_0_0_/_72%)_inset,0_0_42px_oklch(0.64_0.17_170_/_18%)]">
              <div className="grid h-9 w-9 shrink-0 place-items-center">
                <AgentOrb thinking={agentMutation.isPending} active className="h-7 w-7" />
              </div>
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    submit();
                  }
                }}
                rows={1}
                className="max-h-20 min-h-10 flex-1 resize-none bg-transparent px-1 py-2.5 text-sm text-foreground outline-none"
              />
              <Button
                size="icon"
                className="h-10 w-10 rounded-full bg-primary text-primary-foreground shadow-[0_0_20px_oklch(0.64_0.17_170_/_20%)] hover:bg-primary/92"
                onClick={() => submit()}
                disabled={!input.trim() || agentMutation.isPending}
                aria-label="发送"
              >
                {agentMutation.isPending ? <Loader2 size={17} className="animate-spin" /> : <Send size={17} />}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-10 w-10 rounded-full text-muted-foreground hover:bg-primary/8 hover:text-primary"
                onClick={onClose}
                aria-label="关闭"
              >
                <X size={17} />
              </Button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export function AgentLayer() {
  const [open, setOpen] = useState(false);
  const [pressed, setPressed] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const dragState = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    moved: boolean;
  } | null>(null);
  const { data: today } = useQuery({
    queryKey: ["agent-today-checkin"],
    queryFn: () => getTodayCheckIn(),
    retry: false,
  });

  const ariaLabel = useMemo(() => {
    if (today) return "打开知曜 AI 工作流，今天已经整理过学习记录";
    return "打开知曜 AI 工作流，整理今天的学习记录";
  }, [today]);

  useEffect(() => {
    queueMicrotask(() => {
      try {
        const saved = localStorage.getItem("zhiyao_agent_position");
        if (!saved) return;
        const parsed = JSON.parse(saved) as { x?: number; y?: number };
        if (typeof parsed.x === "number" && typeof parsed.y === "number") {
          setPosition({
            x: Math.min(Math.max(16, parsed.x), window.innerWidth - 72),
            y: Math.min(Math.max(72, parsed.y), window.innerHeight - 88),
          });
        }
      } catch {}
    });
  }, []);

  function openPanel() {
    setPressed(true);
    window.setTimeout(() => setPressed(false), 420);
    setOpen(true);
  }

  function getDefaultPosition() {
    if (typeof window === "undefined") return { x: 0, y: 0 };
    return {
      x: window.innerWidth - 76,
      y: window.innerHeight - 160,
    };
  }

  function handlePointerDown(event: React.PointerEvent<HTMLButtonElement>) {
    const fallback = position ?? getDefaultPosition();
    setPosition(fallback);
    setDragging(true);
    dragState.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: fallback.x,
      originY: fallback.y,
      moved: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: React.PointerEvent<HTMLButtonElement>) {
    const state = dragState.current;
    if (!state || state.pointerId !== event.pointerId) return;
    const dx = event.clientX - state.startX;
    const dy = event.clientY - state.startY;
    if (Math.abs(dx) + Math.abs(dy) > 6) state.moved = true;
    const damping = 0.72;
    const next = {
      x: Math.min(Math.max(16, state.originX + dx * damping), window.innerWidth - 72),
      y: Math.min(Math.max(72, state.originY + dy * damping), window.innerHeight - 88),
    };
    setPosition(next);
  }

  function handlePointerUp(event: React.PointerEvent<HTMLButtonElement>) {
    const state = dragState.current;
    if (!state || state.pointerId !== event.pointerId) return;
    dragState.current = null;
    setDragging(false);
    const current = position ?? getDefaultPosition();
    const snapped = state.moved
      ? {
          x: current.x + 28 < window.innerWidth / 2 ? 16 : window.innerWidth - 72,
          y: Math.min(Math.max(72, current.y), window.innerHeight - 88),
        }
      : current;
    setPosition(snapped);
    try {
      localStorage.setItem("zhiyao_agent_position", JSON.stringify(snapped));
    } catch {}
    if (!state.moved) openPanel();
  }

  return (
    <>
      <button
        type="button"
        aria-label={ariaLabel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={() => {
          dragState.current = null;
          setDragging(false);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openPanel();
          }
        }}
        className={cn(
          "fixed z-40 grid h-14 w-14 touch-none place-items-center rounded-full bg-transparent hover:-translate-y-0.5 hover:drop-shadow-[0_10px_24px_oklch(0.64_0.17_170_/_34%)] cursor-grab active:cursor-grabbing",
          dragging
            ? "transition-[filter,transform] duration-150 ease-out"
            : "transition-[left,top,transform,filter] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]"
        )}
        style={
          position
            ? { left: position.x, top: position.y }
            : { right: "1.25rem", bottom: "calc(6rem + env(safe-area-inset-bottom))" }
        }
      >
        <AgentOrb active={!today} pressed={pressed} className="h-9 w-9" />
      </button>
      <AgentCommandPanel open={open} onClose={() => setOpen(false)} />
    </>
  );
}
