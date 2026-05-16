"use client";
import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  CheckSquare, Timer, Play, Pause, RotateCcw,
  Sparkles, CheckCircle2, Circle, Coffee
} from "lucide-react";

type TaskType = "flashcard_review" | "mistake_review" | "manual" | "training";
interface Task {
  id: string; title: string; type: TaskType;
  subject?: string; duration?: number; done: boolean; priority: "high" | "normal";
}

const INITIAL_TASKS: Task[] = [
  { id: "1", title: "闪卡复习：物理 (12张到期)", type: "flashcard_review", subject: "物理", duration: 15, done: false, priority: "high" },
  { id: "2", title: "错题重练：化学电解质", type: "mistake_review", subject: "化学", duration: 10, done: false, priority: "high" },
  { id: "3", title: "训练：数学函数与导数", type: "training", subject: "数学", duration: 25, done: false, priority: "normal" },
  { id: "4", title: "闪卡复习：英语 (8张到期)", type: "flashcard_review", subject: "英语", duration: 10, done: true, priority: "normal" },
  { id: "5", title: "笔记复习：牛顿三大定律", type: "manual", subject: "物理", duration: 20, done: false, priority: "normal" },
];

const TYPE_ICONS: Record<TaskType, string> = {
  flashcard_review: "🃏",
  mistake_review: "❌",
  training: "🎯",
  manual: "📖",
};

const PRIORITY_COLORS = {
  high: "bg-red-100 text-red-600",
  normal: "bg-muted text-muted-foreground",
};

// Pomodoro: 25 min work, 5 min break
const WORK_SECONDS = 25 * 60;
const BREAK_SECONDS = 5 * 60;

function pad(n: number) { return String(n).padStart(2, "0"); }

function PomodoroTimer() {
  const [seconds, setSeconds] = useState(WORK_SECONDS);
  const [running, setRunning] = useState(false);
  const [mode, setMode] = useState<"work" | "break">("work");
  const [sessions, setSessions] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const total = mode === "work" ? WORK_SECONDS : BREAK_SECONDS;
  const progress = ((total - seconds) / total) * 100;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;

  useEffect(() => {
    if (running) {
      intervalRef.current = setInterval(() => {
        setSeconds((s) => {
          if (s <= 1) {
            clearInterval(intervalRef.current!);
            setRunning(false);
            if (mode === "work") {
              setSessions((n) => n + 1);
              setMode("break");
              return BREAK_SECONDS;
            } else {
              setMode("work");
              return WORK_SECONDS;
            }
          }
          return s - 1;
        });
      }, 1000);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [running, mode]);

  function reset() {
    setRunning(false);
    setMode("work");
    setSeconds(WORK_SECONDS);
  }

  // SVG circle
  const R = 52;
  const circ = 2 * Math.PI * R;
  const offset = circ * (1 - progress / 100);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Timer size={16} className="text-primary" /> 番茄钟
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Mode tab */}
        <div className="flex gap-1 p-1 bg-muted rounded-lg">
          {(["work", "break"] as const).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setSeconds(m === "work" ? WORK_SECONDS : BREAK_SECONDS); setRunning(false); }}
              className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all ${
                mode === m ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"
              }`}
            >
              {m === "work" ? "专注 25min" : "休息 5min"}
            </button>
          ))}
        </div>

        {/* Circle timer */}
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <svg width="130" height="130" className="-rotate-90">
              <circle cx="65" cy="65" r={R} fill="none" stroke="hsl(var(--muted))" strokeWidth="8" />
              <circle
                cx="65" cy="65" r={R} fill="none"
                stroke={mode === "work" ? "hsl(var(--primary))" : "hsl(142 76% 36%)"}
                strokeWidth="8"
                strokeDasharray={circ}
                strokeDashoffset={offset}
                strokeLinecap="round"
                className="transition-all duration-1000"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-bold font-mono text-foreground">
                {pad(mins)}:{pad(secs)}
              </span>
              <span className="text-[11px] text-muted-foreground">
                {mode === "work" ? "专注中" : "休息中"}
              </span>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              size="icon"
              variant="outline"
              onClick={() => setRunning((r) => !r)}
              className="w-10 h-10"
            >
              {running ? <Pause size={16} /> : <Play size={16} />}
            </Button>
            <Button size="icon" variant="outline" onClick={reset} className="w-10 h-10">
              <RotateCcw size={14} />
            </Button>
          </div>
        </div>

        {/* Session count */}
        <div className="flex items-center justify-between text-sm border-t border-border pt-3">
          <span className="text-muted-foreground flex items-center gap-1.5">
            <Coffee size={13} /> 今日番茄数
          </span>
          <div className="flex gap-1">
            {Array.from({ length: Math.min(sessions + 2, 8) }).map((_, i) => (
              <div
                key={i}
                className={`w-2.5 h-2.5 rounded-full ${i < sessions ? "bg-primary" : "bg-muted"}`}
              />
            ))}
          </div>
          <span className="font-semibold text-foreground">{sessions} 个</span>
        </div>
      </CardContent>
    </Card>
  );
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>(INITIAL_TASKS);
  const [generating, setGenerating] = useState(false);

  const done = tasks.filter((t) => t.done).length;
  const total = tasks.length;
  const progress = (done / total) * 100;

  function toggleTask(id: string) {
    setTasks((prev) =>
      prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t))
    );
  }

  function handleGenerate() {
    setGenerating(true);
    setTimeout(() => setGenerating(false), 1200);
  }

  const pendingTasks = tasks.filter((t) => !t.done);
  const doneTasks = tasks.filter((t) => t.done);

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-5 md:space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">每日任务</h1>
          <p className="text-sm text-muted-foreground mt-0.5">今天，{new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "long" })}</p>
        </div>
        <Button onClick={handleGenerate} disabled={generating} variant="outline" className="gap-2">
          <Sparkles size={15} className={generating ? "animate-spin" : ""} />
          {generating ? "AI 生成中…" : "AI 重排任务"}
        </Button>
      </div>

      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">今日进度</span>
          <span className="font-medium text-foreground">{done} / {total} 完成</span>
        </div>
        <Progress value={progress} className="h-2" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
        {/* Task list */}
        <div className="md:col-span-2 space-y-4">
          {/* Pending */}
          <div className="space-y-2">
            {pendingTasks.map((task) => (
              <div
                key={task.id}
                className="flex items-start gap-3 p-3.5 rounded-xl border border-border bg-card hover:border-primary/30 transition-colors cursor-pointer group"
                onClick={() => toggleTask(task.id)}
              >
                <button className="mt-0.5 shrink-0 text-muted-foreground group-hover:text-primary transition-colors">
                  <Circle size={18} />
                </button>
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-base">{TYPE_ICONS[task.type]}</span>
                    <span className="text-sm font-medium text-foreground">{task.title}</span>
                    {task.priority === "high" && (
                      <span className={`text-[11px] px-1.5 py-0.5 rounded-full font-medium ${PRIORITY_COLORS.high}`}>
                        优先
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {task.subject && <span>{task.subject}</span>}
                    {task.duration && <span>· 约 {task.duration} 分钟</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Done tasks */}
          {doneTasks.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground px-1">已完成</p>
              {doneTasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-start gap-3 p-3.5 rounded-xl border border-border bg-muted/30 cursor-pointer opacity-60 hover:opacity-80 transition-opacity"
                  onClick={() => toggleTask(task.id)}
                >
                  <CheckCircle2 size={18} className="text-green-500 mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-muted-foreground line-through">{task.title}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {pendingTasks.length === 0 && doneTasks.length === total && (
            <div className="text-center py-10 space-y-2">
              <CheckCircle2 size={36} className="mx-auto text-green-500" />
              <p className="font-semibold text-foreground">今日任务全部完成！</p>
              <p className="text-sm text-muted-foreground">太棒了，好好休息吧。</p>
            </div>
          )}
        </div>

        {/* Pomodoro */}
        <div>
          <PomodoroTimer />
        </div>
      </div>
    </div>
  );
}
