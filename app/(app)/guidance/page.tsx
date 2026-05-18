"use client";
import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { MessageCircle, Send, Loader2, Plus, Brain, Lightbulb, History } from "lucide-react";
import { cn } from "@/lib/utils";
import { startGuidance, chatGuidance, listGuidanceSessions } from "@/lib/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: boolean;
}

const SUBJECTS = ["不限", "数学", "物理", "化学", "生物", "英语", "语文"];

const WELCOME: Message = {
  id: "0",
  role: "assistant",
  content: "你好！我是你的学习引导助手。我会用苏格拉底式问答帮你深度理解知识，而不是直接给你答案。\n\n你有什么不明白的概念，或想深入探讨的问题吗？",
};

export default function GuidancePage() {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [subject, setSubject] = useState("不限");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const { data: sessionsData } = useQuery({
    queryKey: ["guidance-sessions"],
    queryFn: () => listGuidanceSessions(),
  });

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: text };
    const thinkingMsg: Message = { id: "thinking", role: "assistant", content: "", thinking: true };
    setMessages((prev) => [...prev, userMsg, thinkingMsg]);
    setInput("");
    setLoading(true);

    try {
      let aiContent: string;

      if (!sessionId) {
        // 第一条消息：创建新会话
        const res = await startGuidance({
          question: text,
          subject: subject === "不限" ? undefined : subject,
        });
        setSessionId(res.session_id);
        aiContent = res.message.content;
      } else {
        // 后续消息：继续对话
        const res = await chatGuidance(sessionId, text);
        aiContent = res.message.content;
      }

      setMessages((prev) => [
        ...prev.filter((m) => m.id !== "thinking"),
        { id: (Date.now() + 1).toString(), role: "assistant", content: aiContent },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== "thinking"),
        { id: `err-${Date.now()}`, role: "assistant", content: "连接出现问题，请稍后再试。" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleNewSession() {
    setMessages([WELCOME]);
    setInput("");
    setSessionId(null);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const sessions: { id: string; title: string; subject: string | null }[] =
    sessionsData?.items ?? [];

  return (
    <div className="h-[calc(100vh-56px)] md:h-screen flex">
      {/* Sidebar */}
      <div className="hidden md:flex w-64 border-r border-border flex-col bg-sidebar">
        <div className="p-4 border-b border-sidebar-border">
          <h2 className="font-semibold text-sm text-sidebar-foreground flex items-center gap-2">
            <MessageCircle size={15} className="text-primary" /> 引导问答
          </h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">苏格拉底式引导学习</p>
        </div>

        <div className="p-3 border-b border-sidebar-border">
          <Button onClick={handleNewSession} variant="outline" size="sm" className="w-full gap-2">
            <Plus size={13} /> 新会话
          </Button>
        </div>

        {/* Subject */}
        <div className="p-3 border-b border-sidebar-border space-y-1">
          <p className="text-[11px] font-medium text-muted-foreground px-1">学科（下次会话生效）</p>
          {SUBJECTS.map((s) => (
            <button
              key={s}
              onClick={() => setSubject(s)}
              className={cn(
                "w-full text-left px-3 py-1.5 rounded-md text-sm transition-colors",
                subject === s
                  ? "bg-sidebar-accent text-sidebar-primary font-medium"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/60"
              )}
            >
              {s}
            </button>
          ))}
        </div>

        {/* History */}
        {sessions.length > 0 && (
          <div className="p-3 flex-1 overflow-y-auto">
            <p className="text-[11px] font-medium text-muted-foreground px-1 mb-1.5 flex items-center gap-1">
              <History size={11} /> 历史会话
            </p>
            {sessions.slice(0, 10).map((s) => (
              <div key={s.id} className="px-3 py-1.5 rounded-md text-xs text-muted-foreground truncate hover:bg-sidebar-accent/60 cursor-default">
                {s.title ?? "未命名会话"}
              </div>
            ))}
          </div>
        )}

        <div className="mt-auto p-3">
          <div className="p-3 rounded-lg bg-primary/5 border border-primary/15 space-y-1.5">
            <p className="text-[11px] font-medium text-primary flex items-center gap-1.5">
              <Lightbulb size={12} /> 使用技巧
            </p>
            <ul className="text-[11px] text-muted-foreground space-y-0.5">
              <li>· 描述你的困惑点，而非问&quot;是什么&quot;</li>
              <li>· 回答 AI 的反问，触发更深引导</li>
              <li>· 用自己的话解释概念</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn("flex gap-3 max-w-2xl", msg.role === "user" ? "ml-auto flex-row-reverse" : "")}
            >
              {msg.role === "assistant" && (
                <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center shrink-0 mt-0.5">
                  <Brain size={14} className="text-primary-foreground" />
                </div>
              )}
              <div
                className={cn(
                  "rounded-2xl px-4 py-3 text-sm leading-relaxed max-w-[85%]",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground rounded-tr-sm"
                    : "bg-card border border-border text-foreground rounded-tl-sm",
                  msg.thinking && "animate-pulse"
                )}
              >
                {msg.thinking ? (
                  <div className="flex gap-1 items-center py-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:0ms]" />
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:150ms]" />
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:300ms]" />
                  </div>
                ) : (
                  <p className="whitespace-pre-line">{msg.content}</p>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 border-t border-border bg-background">
          <div className="flex gap-3 items-end max-w-3xl mx-auto">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="描述你不理解的概念或困惑… (Enter 发送，Shift+Enter 换行)"
                rows={1}
                className="w-full resize-none rounded-xl border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 min-h-[48px] max-h-[160px] overflow-y-auto"
                onInput={(e) => {
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = Math.min(el.scrollHeight, 160) + "px";
                }}
              />
            </div>
            <Button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              size="icon"
              className="h-12 w-12 rounded-xl shrink-0"
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </Button>
          </div>
          <p className="text-center text-[11px] text-muted-foreground mt-2">
            DeepSeek V4 Flash · 苏格拉底式引导，不直接给答案
          </p>
        </div>
      </div>
    </div>
  );
}
