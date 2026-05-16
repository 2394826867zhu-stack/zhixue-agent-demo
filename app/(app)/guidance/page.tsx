"use client";
import { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MessageCircle, Send, Loader2, Plus, Brain, Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: boolean;
}

const INITIAL_MESSAGES: Message[] = [
  {
    id: "0",
    role: "assistant",
    content: "你好！我是你的学习引导助手。我会用苏格拉底式问答来帮助你深度理解知识，而不是直接给你答案。\n\n你有什么不明白的概念，或者想深入探讨的问题吗？",
  },
];

const SUBJECTS = ["数学", "物理", "化学", "生物", "英语", "语文", "不限"];

// Simulated AI response logic
function getMockResponse(question: string): string {
  const q = question.toLowerCase();
  if (q.includes("动量") || q.includes("守恒")) {
    return `好问题！在我回答之前，我想先问问你：你认为"守恒"这个词的含义是什么？在什么情况下，你会说一个量是"守恒"的？`;
  }
  if (q.includes("极限") || q.includes("无穷")) {
    return `有意思！让我们先从直觉出发。如果我告诉你，当 x 越来越接近 0 时，sin(x)/x 会趋近于某个值——你觉得这个值会比 1 大，还是比 1 小？你是怎么判断的？`;
  }
  if (q.includes("细胞") || q.includes("分裂")) {
    return `好，在深入讲解之前，我想问你：你平时理解的"复制"和"分裂"有什么区别？细胞分裂时，什么东西需要先被"复制"？`;
  }
  return `这是个很好的问题。在给你解释之前，我想先了解一下你已经知道什么。关于这个概念，你目前的理解是什么？哪个部分让你感到困惑？`;
}

export default function GuidancePage() {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [subject, setSubject] = useState("不限");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: text };
    const thinkingMsg: Message = { id: "thinking", role: "assistant", content: "", thinking: true };

    setMessages((prev) => [...prev, userMsg, thinkingMsg]);
    setInput("");
    setLoading(true);

    await new Promise((r) => setTimeout(r, 1400));

    const response = getMockResponse(text);
    setMessages((prev) => [
      ...prev.filter((m) => m.id !== "thinking"),
      { id: (Date.now() + 1).toString(), role: "assistant", content: response },
    ]);
    setLoading(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleNewSession() {
    setMessages(INITIAL_MESSAGES);
    setInput("");
  }

  return (
    <div className="h-[calc(100vh-56px)] md:h-screen flex">
      {/* Sidebar panel — hidden on mobile */}
      <div className="hidden md:flex w-64 border-r border-border flex-col bg-sidebar">
        <div className="p-4 border-b border-sidebar-border">
          <h2 className="font-semibold text-sm text-sidebar-foreground flex items-center gap-2">
            <MessageCircle size={15} className="text-primary" /> 引导问答
          </h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">苏格拉底式引导学习</p>
        </div>

        {/* New session */}
        <div className="p-3 border-b border-sidebar-border">
          <Button onClick={handleNewSession} variant="outline" size="sm" className="w-full gap-2">
            <Plus size={13} /> 新会话
          </Button>
        </div>

        {/* Subject filter */}
        <div className="p-3 space-y-1.5">
          <p className="text-[11px] font-medium text-muted-foreground px-1">学科</p>
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

        {/* Tips */}
        <div className="mt-auto p-3">
          <div className="p-3 rounded-lg bg-primary/5 border border-primary/15 space-y-2">
            <p className="text-[11px] font-medium text-primary flex items-center gap-1.5">
              <Lightbulb size={12} /> 使用技巧
            </p>
            <ul className="text-[11px] text-muted-foreground space-y-1">
              <li>· 描述你的困惑点，而非问"是什么"</li>
              <li>· 回答AI的反问，触发更深引导</li>
              <li>· 尝试用自己的话解释概念</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-h-0">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn("flex gap-3 max-w-2xl", msg.role === "user" ? "ml-auto flex-row-reverse" : "")}
            >
              {/* Avatar */}
              {msg.role === "assistant" && (
                <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center shrink-0 mt-0.5">
                  <Brain size={14} className="text-primary-foreground" />
                </div>
              )}

              {/* Bubble */}
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

        {/* Input area */}
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
                style={{ height: "auto" }}
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
            AI 会引导你思考，而非直接给出答案
          </p>
        </div>
      </div>
    </div>
  );
}
