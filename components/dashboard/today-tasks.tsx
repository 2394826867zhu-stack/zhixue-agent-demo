"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Circle, Layers, AlertCircle, PenLine, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const TASKS = [
  { id: 1, title: "复习数学闪卡（12张）", type: "flashcard_review", subject: "数学", minutes: 24, priority: "high", done: false },
  { id: 2, title: "错题重练·物理（3题）", type: "mistake_review", subject: "物理", minutes: 15, priority: "high", done: false },
  { id: 3, title: "复习英语闪卡（8张）", type: "flashcard_review", subject: "英语", minutes: 16, priority: "medium", done: true },
  { id: 4, title: "背高考化学方程式", type: "manual", subject: "化学", minutes: 25, priority: "medium", done: false },
  { id: 5, title: "错题重练·语文（2题）", type: "mistake_review", subject: "语文", minutes: 10, priority: "low", done: false },
];

const TYPE_ICON: Record<string, React.ElementType> = {
  flashcard_review: Layers,
  mistake_review: AlertCircle,
  manual: PenLine,
};

const PRIORITY_COLOR: Record<string, string> = {
  high: "text-rose-500",
  medium: "text-amber-500",
  low: "text-slate-400",
};

export function TodayTasks() {
  const [tasks, setTasks] = useState(TASKS);
  const done = tasks.filter((t) => t.done).length;

  const toggle = (id: number) =>
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t)));

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold">今日任务</CardTitle>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{done}/{tasks.length} 完成</span>
            <button className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors">
              <Sparkles size={12} />
              AI生成
            </button>
          </div>
        </div>
        {/* progress bar */}
        <div className="h-1 bg-muted rounded-full mt-2">
          <div
            className="h-1 bg-primary rounded-full transition-all duration-500"
            style={{ width: `${(done / tasks.length) * 100}%` }}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-1">
        {tasks.map((task) => {
          const Icon = TYPE_ICON[task.type] || PenLine;
          return (
            <div
              key={task.id}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer group transition-colors",
                task.done ? "opacity-50" : "hover:bg-muted/60"
              )}
              onClick={() => toggle(task.id)}
            >
              {task.done ? (
                <CheckCircle2 size={16} className="text-primary shrink-0" />
              ) : (
                <Circle size={16} className="text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
              )}
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <Icon size={13} className={cn("shrink-0", PRIORITY_COLOR[task.priority])} />
                <span className={cn("text-sm truncate", task.done && "line-through text-muted-foreground")}>
                  {task.title}
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                  {task.subject}
                </Badge>
                <span className="text-[10px] text-muted-foreground">{task.minutes}min</span>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
