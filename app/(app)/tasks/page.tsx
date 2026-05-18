"use client";
import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  CheckSquare, Timer, Play, Pause, RotateCcw,
  Sparkles, CheckCircle2, Coffee, Plus, Loader2,
  Layers, AlertCircle, Target, BookOpen, ClipboardList, Lightbulb
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { getTodayTasks, updateTask, generateTasks, createTask, recordPomodoro } from "@/lib/api";

interface Task {
  id: string;
  title: string;
  task_type: string;
  subject?: string;
  estimated_minutes?: number;
  priority?: string;
  status: string;
  is_done: boolean;
  ai_priority_reason?: string;
}

const TYPE_ICONS: Record<string, LucideIcon> = {
  flashcard_review: Layers,
  mistake_review: AlertCircle,
  training: Target,
  manual: BookOpen,
};

function taskHref(task: Task) {
  if (task.task_type === "flashcard_review") return "/flashcards";
  if (task.task_type === "mistake_review") return "/mistakes";
  if (task.task_type === "training") return task.subject ? `/training?subject=${encodeURIComponent(task.subject)}` : "/training";
  return task.subject ? `/knowledge?subject=${encodeURIComponent(task.subject)}` : "/knowledge";
}

const WORK_SECONDS = 25 * 60;
const BREAK_SECONDS = 5 * 60;

function pad(n: number) { return String(n).padStart(2, "0"); }

function PomodoroTimer({ onSessionComplete }: { onSessionComplete?: (mins: number) => void }) {
  const [seconds, setSeconds] = useState(WORK_SECONDS);
  const [running, setRunning] = useState(false);
  const [mode, setMode] = useState<"work" | "break">("work");
  const [sessions, setSessions] = useState(0);
  const startedAtRef = useRef<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Keep callback in a ref so changing it never recreates the interval
  const onSessionCompleteRef = useRef(onSessionComplete);
  useEffect(() => { onSessionCompleteRef.current = onSessionComplete; });

  const total = mode === "work" ? WORK_SECONDS : BREAK_SECONDS;
  const progress = ((total - seconds) / total) * 100;
  const R = 52;
  const circ = 2 * Math.PI * R;
  const offset = circ * (1 - progress / 100);

  useEffect(() => {
    if (running) {
      if (!startedAtRef.current) startedAtRef.current = new Date();
      intervalRef.current = setInterval(() => {
        setSeconds((s) => {
          if (s <= 1) {
            clearInterval(intervalRef.current!);
            setRunning(false);
            if (mode === "work") {
              const durationMins = 25;
              setSessions((n) => n + 1);
              onSessionCompleteRef.current?.(durationMins);
              startedAtRef.current = null;
              setMode("break");
              return BREAK_SECONDS;
            } else {
              startedAtRef.current = null;
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
  }, [running, mode]); // onSessionComplete intentionally excluded — accessed via ref

  function reset() {
    setRunning(false);
    setMode("work");
    setSeconds(WORK_SECONDS);
    startedAtRef.current = null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Timer size={16} className="text-primary" /> 番茄钟
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex gap-1 p-1 bg-muted rounded-lg">
          {(["work", "break"] as const).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setSeconds(m === "work" ? WORK_SECONDS : BREAK_SECONDS); setRunning(false); startedAtRef.current = null; }}
              className={cn(
                "flex-1 py-1.5 rounded-md text-xs font-medium transition-all",
                mode === m ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"
              )}
            >
              {m === "work" ? "专注 25min" : "休息 5min"}
            </button>
          ))}
        </div>

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
                {pad(Math.floor(seconds / 60))}:{pad(seconds % 60)}
              </span>
              <span className="text-[11px] text-muted-foreground">
                {running ? (mode === "work" ? "专注中" : "休息中") : "已暂停"}
              </span>
            </div>
          </div>

          <div className="flex gap-2">
            <Button size="icon" variant="outline" onClick={() => setRunning((r) => !r)} className="w-10 h-10">
              {running ? <Pause size={16} /> : <Play size={16} />}
            </Button>
            <Button size="icon" variant="outline" onClick={reset} className="w-10 h-10">
              <RotateCcw size={14} />
            </Button>
          </div>
        </div>

        <div className="flex items-center justify-between text-sm border-t border-border pt-3">
          <span className="text-muted-foreground flex items-center gap-1.5">
            <Coffee size={13} /> 今日番茄数
          </span>
          <div className="flex gap-1">
            {Array.from({ length: Math.min(sessions + 2, 8) }).map((_, i) => (
              <div key={i} className={cn("w-2.5 h-2.5 rounded-full", i < sessions ? "bg-primary" : "bg-muted")} />
            ))}
          </div>
          <span className="font-semibold text-foreground">{sessions} 个</span>
        </div>
      </CardContent>
    </Card>
  );
}

export default function TasksPage() {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [generateNotice, setGenerateNotice] = useState<string | null>(null);

  const { data: tasks = [], isLoading } = useQuery<Task[]>({
    queryKey: ["today-tasks"],
    queryFn: () => getTodayTasks() as Promise<Task[]>,
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_done }: { id: string; is_done: boolean }) =>
      updateTask(id, { status: is_done ? "pending" : "done" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["today-tasks"] }),
    onError: () => queryClient.invalidateQueries({ queryKey: ["today-tasks"] }),
  });

  const generateMut = useMutation({
    mutationFn: () => generateTasks(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["today-tasks"] });
      if (!data || (Array.isArray(data) && data.length === 0)) {
        setGenerateNotice("暂无可生成任务，先添加笔记或知识点");
      } else {
        setGenerateNotice("已生成今日任务");
      }
    },
    onError: () => setGenerateNotice("生成失败，请稍后重试"),
  });

  const createMut = useMutation({
    mutationFn: (title: string) => createTask({ title }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["today-tasks"] });
      setNewTitle("");
      setShowAdd(false);
    },
    onError: () => queryClient.invalidateQueries({ queryKey: ["today-tasks"] }),
  });

  function handlePomodoroComplete(durationMins: number) {
    const now = new Date();
    const startedAt = new Date(now.getTime() - durationMins * 60 * 1000);
    recordPomodoro({
      duration_minutes: durationMins,
      started_at: startedAt.toISOString(),
      completed_at: now.toISOString(),
    }).catch(() => {});
  }

  const pendingTasks = tasks.filter((t) => !t.is_done);
  const doneTasks = tasks.filter((t) => t.is_done);
  const done = doneTasks.length;
  const total = tasks.length;
  const progress = total > 0 ? (done / total) * 100 : 0;

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-5 md:space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">每日任务</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            今天，{new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "long" })}
          </p>
        </div>
        <Button
          onClick={() => generateMut.mutate()}
          disabled={generateMut.isPending}
          variant="outline"
          className="gap-2"
        >
          {generateMut.isPending
            ? <><Loader2 size={15} className="animate-spin" /> 生成中…</>
            : <><Sparkles size={15} /> AI 生成任务</>}
        </Button>
      </div>
      {generateMut.isError && (
        <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/8 border border-destructive/20 rounded-lg px-3 py-2.5">
          <AlertCircle size={14} /> 任务生成失败，请稍后重试
        </div>
      )}
      {generateNotice && !generateMut.isError && (
        <div className="flex items-center gap-2 rounded-lg border border-primary/15 bg-primary/6 px-3 py-2.5 text-sm text-muted-foreground">
          <Lightbulb size={14} className="text-primary" /> {generateNotice}
        </div>
      )}

      {total > 0 && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">今日进度</span>
            <span className="font-medium text-foreground">{done} / {total} 完成</span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
        <div className="md:col-span-2 space-y-4">
          {isLoading && (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 size={20} className="animate-spin mr-2" /> 加载中…
            </div>
          )}

          {!isLoading && pendingTasks.length === 0 && doneTasks.length === 0 && (
            <div className="rounded-2xl border border-dashed border-border bg-card px-5 py-10 text-center">
              <CheckSquare size={36} className="mx-auto text-primary/55" />
              <p className="mt-3 font-semibold text-foreground">今日还没有任务</p>
              <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
                让 AI 根据你的知识点、错题和临近考试生成一组今天能完成的小任务。
              </p>
              <Button onClick={() => generateMut.mutate()} disabled={generateMut.isPending} className="mt-5 gap-2">
                {generateMut.isPending ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
                AI 生成今日任务
              </Button>
            </div>
          )}

          {pendingTasks.length > 0 && (
            <div className="space-y-3">
              {pendingTasks.map((task, index) => {
                const TypeIcon = TYPE_ICONS[task.task_type] ?? ClipboardList;
                return (
                <div
                  key={task.id}
                  className="grid gap-3 rounded-2xl border border-border bg-card p-4 transition-colors hover:border-primary/30 md:grid-cols-[auto_minmax(0,1fr)_auto]"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold tabular-nums text-primary" aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-primary">
                        <TypeIcon size={13} />
                      </span>
                      <span className="text-sm font-medium text-foreground">{task.title}</span>
                      {task.priority === "high" && (
                        <span className="text-[11px] px-1.5 py-0.5 rounded-full font-medium bg-red-100 text-red-600">优先</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      {task.subject && <span>{task.subject}</span>}
                      {task.estimated_minutes && <span>· 约 {task.estimated_minutes} 分钟</span>}
                    </div>
                    {task.ai_priority_reason && (
                      <p className="flex gap-1.5 text-xs text-muted-foreground/80 leading-relaxed line-clamp-2">
                        <Lightbulb size={12} className="mt-0.5 shrink-0 text-primary/75" />
                        <span>{task.ai_priority_reason}</span>
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2 md:flex-col md:items-stretch">
                    <Link
                      href={taskHref(task)}
                      className="inline-flex h-9 items-center justify-center gap-1.5 rounded-xl bg-primary px-3 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
                    >
                      <Play size={13} /> 去完成
                    </Link>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-9 gap-1.5 px-3 text-xs"
                      onClick={() => toggleMut.mutate({ id: task.id, is_done: task.is_done })}
                      disabled={toggleMut.isPending}
                    >
                      <CheckCircle2 size={13} /> 完成
                    </Button>
                  </div>
                </div>
                );
              })}
            </div>
          )}

          {/* Add task */}
          <div>
            {!showAdd ? (
              <button
                onClick={() => setShowAdd(true)}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors px-1 py-1.5"
              >
                <Plus size={15} /> 添加任务
              </button>
            ) : (
              <div className="flex gap-2">
                <input
                  autoFocus
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && newTitle.trim()) createMut.mutate(newTitle.trim());
                    if (e.key === "Escape") { setShowAdd(false); setNewTitle(""); }
                  }}
                  placeholder="任务名称…"
                  className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
                <Button
                  size="sm"
                  onClick={() => newTitle.trim() && createMut.mutate(newTitle.trim())}
                  disabled={!newTitle.trim() || createMut.isPending}
                >
                  {createMut.isPending ? <Loader2 size={13} className="animate-spin" /> : "添加"}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => { setShowAdd(false); setNewTitle(""); }}>取消</Button>
              </div>
            )}
          </div>

          {doneTasks.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground px-1">已完成</p>
              {doneTasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-start justify-between gap-3 rounded-xl border border-border bg-muted/30 p-3.5 opacity-70"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <CheckCircle2 size={18} className="text-green-500 mt-0.5 shrink-0" />
                    <p className="text-sm text-muted-foreground line-through">{task.title}</p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 shrink-0 text-xs"
                    onClick={() => toggleMut.mutate({ id: task.id, is_done: task.is_done })}
                  >
                    恢复
                  </Button>
                </div>
              ))}
            </div>
          )}

          {!isLoading && pendingTasks.length === 0 && doneTasks.length > 0 && (
            <div className="text-center py-6 space-y-1">
              <CheckCircle2 size={32} className="mx-auto text-green-500" />
              <p className="font-semibold text-foreground">今日任务全部完成！</p>
              <p className="text-sm text-muted-foreground">太棒了，好好休息吧。</p>
            </div>
          )}
        </div>

        <div>
          <PomodoroTimer onSessionComplete={handlePomodoroComplete} />
        </div>
      </div>
    </div>
  );
}
