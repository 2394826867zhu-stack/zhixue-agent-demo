"use client";
import { useState } from "react";
import { Sparkles, ArrowRight } from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { api, isDemoMode } from "@/lib/api";

const QUICK_GOALS = [
  "备战期末考试",
  "准备高考",
  "提升英语水平",
  "系统复习薄弱科目",
];

export function GoalDialog() {
  const { user, learningGoal, setLearningGoal } = useAuthStore();
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);

  // 已登录且已设置目标 → 不显示
  if (!user || learningGoal) return null;

  async function handleConfirm(goal: string) {
    const g = goal.trim();
    if (!g) return;
    setSaving(true);
    setLearningGoal(g);
    // 触发后台 AI 路径生成，不阻塞 UI
    if (!isDemoMode()) {
      api.post("/path/ai-generate", { goal: g }).catch(() => {});
    }
    setSaving(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-[1.75rem] border border-border/80 bg-card shadow-[0_24px_64px_oklch(0_0_0_/_18%)] p-6 space-y-5">
        {/* 头部 */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/12 text-primary">
            <Sparkles size={20} />
          </div>
          <div>
            <p className="font-bold text-foreground">你好，{user.nickname || user.username} 👋</p>
            <p className="text-xs text-muted-foreground">告诉知曜你现在在准备什么</p>
          </div>
        </div>

        {/* 输入 */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">
            你最近在准备什么考试或学习目标？
          </label>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleConfirm(input)}
            placeholder="例如：备战期末、提升数学成绩…"
            className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none ring-0 transition focus:border-primary/40 focus:ring-4 focus:ring-primary/12"
            autoFocus
          />
        </div>

        {/* 快选 */}
        <div className="flex flex-wrap gap-2">
          {QUICK_GOALS.map((g) => (
            <button
              key={g}
              onClick={() => handleConfirm(g)}
              className="rounded-full border border-border/70 bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:border-primary/40 hover:bg-primary/8 hover:text-primary"
            >
              {g}
            </button>
          ))}
        </div>

        {/* 确认 */}
        <Button
          className="w-full gap-2"
          onClick={() => handleConfirm(input)}
          disabled={saving || !input.trim()}
        >
          {saving ? "正在生成学习路径…" : "开始学习"}
          <ArrowRight size={16} />
        </Button>

        <p className="text-center text-xs text-muted-foreground">
          AI 会根据你的目标生成专属路径，随时可以修改
        </p>
      </div>
    </div>
  );
}
