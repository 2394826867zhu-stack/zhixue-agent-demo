"use client";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  Brain,
  CheckCircle2,
  Clock,
  Flame,
  Layers3,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { HeatmapChart } from "@/components/dashboard/heatmap";
import { MasteryRing } from "@/components/dashboard/mastery-ring";
import { SubjectProgress } from "@/components/dashboard/subject-progress";
import { TodayTasks } from "@/components/dashboard/today-tasks";
import { WeeklySummary } from "@/components/dashboard/weekly-summary";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getTodayTasks, getPomodoroStats } from "@/lib/api";

type Task = {
  id: string;
  title: string;
  task_type: string;
  subject?: string;
  estimated_minutes?: number;
  priority?: string;
  is_done: boolean;
  ai_priority_reason?: string;
};

type PomodoroStats = {
  sessions: number;
  focus_minutes: number;
  streak_days: number;
};

function taskIcon(task_type: string) {
  if (task_type === "flashcard_review") return Brain;
  if (task_type === "mistake_review") return Target;
  return BookOpen;
}

function taskHref(task_type: string) {
  if (task_type === "flashcard_review") return "/flashcards";
  if (task_type === "mistake_review") return "/mistakes";
  return "/tasks";
}

export default function DashboardPage() {
  const { data: tasks, isLoading: tasksLoading } = useQuery<Task[]>({
    queryKey: ["today-tasks"],
    queryFn: getTodayTasks,
  });

  const { data: pomodoro } = useQuery<PomodoroStats>({
    queryKey: ["pomodoro-stats"],
    queryFn: getPomodoroStats,
  });

  const dateLabel = new Date().toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  });

  const focusTasks = (tasks ?? []).filter((t) => !t.is_done).slice(0, 3);
  const todayTotal = (tasks ?? []).length;
  const todayDone = (tasks ?? []).filter((t) => t.is_done).length;

  const metricCards = [
    {
      label: "今日计划",
      value: tasksLoading ? "…" : String(todayTotal - todayDone),
      unit: "项",
      icon: CheckCircle2,
      tone: "text-primary",
    },
    {
      label: "预计投入",
      value: tasksLoading
        ? "…"
        : String(
            (tasks ?? [])
              .filter((t) => !t.is_done)
              .reduce((s, t) => s + (t.estimated_minutes ?? 0), 0)
          ),
      unit: "min",
      icon: Clock,
      tone: "text-sky-600",
    },
    {
      label: "连续学习",
      value: pomodoro ? String(pomodoro.streak_days) : "…",
      unit: "天",
      icon: Flame,
      tone: "text-amber-600",
    },
    {
      label: "本周番茄",
      value: pomodoro ? String(pomodoro.sessions) : "…",
      unit: "个",
      icon: Sparkles,
      tone: "text-violet-600",
    },
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
      <section className="overflow-hidden rounded-[1.75rem] border border-border/75 bg-card shadow-[var(--shadow-card)]">
        <div className="grid gap-6 p-5 lg:grid-cols-[1.3fr_0.7fr] md:p-7">
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="bg-primary/10 text-primary">
                今日学习节奏
              </Badge>
              <span className="text-sm font-medium text-muted-foreground">{dateLabel}</span>
            </div>

            <div className="max-w-2xl">
              <h1 className="text-2xl font-bold tracking-normal text-foreground md:text-3xl">
                今天先轻量推进 {focusTasks.length || 3} 件事，保持节奏就好
              </h1>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground md:text-base">
                知曜已根据复习记录、错题和知识点状态，为你排出一个低压力学习顺序。
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <Link href="/tasks" className={cn(buttonVariants({ size: "lg" }), "gap-2")}>
                开始今日计划
                <ArrowRight size={17} />
              </Link>
              <Button variant="outline" size="lg" className="gap-2">
                <RefreshCw size={17} />
                让 AI 重新安排
              </Button>
            </div>
          </div>

          <div className="rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/12 via-card to-card p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-foreground">本周完成</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {todayDone} / {todayTotal} 项任务
                </p>
              </div>
              <div className="rounded-2xl bg-primary/10 p-2 text-primary">
                <Target size={20} />
              </div>
            </div>
            <div className="mt-6">
              <div className="flex items-end justify-between">
                <p className="text-4xl font-bold text-foreground">
                  {todayTotal > 0 ? Math.round((todayDone / todayTotal) * 100) : 0}%
                </p>
                <p className="text-xs font-medium text-muted-foreground">
                  还差 {todayTotal - todayDone} 项
                </p>
              </div>
              <Progress
                value={todayTotal > 0 ? (todayDone / todayTotal) * 100 : 0}
                className="mt-3 h-2.5"
              />
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
        {metricCards.map(({ label, value, unit, icon: Icon, tone }) => (
          <Card key={label} size="sm">
            <CardContent className="py-1">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">{label}</p>
                  <p className="mt-1 text-2xl font-bold text-foreground">
                    {value}
                    <span className="ml-1 text-sm font-semibold text-muted-foreground">{unit}</span>
                  </p>
                </div>
                <div className={`rounded-2xl bg-current/10 p-2 ${tone}`}>
                  <Icon size={18} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <Card className="border-primary/15">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles size={17} className="text-primary" />
                    AI 建议的下一步
                  </CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">
                    每项都控制在可开始的粒度，减少心理负担。
                  </p>
                </div>
                <Badge variant="outline">可调整</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {tasksLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex gap-4 rounded-2xl border border-border/75 bg-background/70 p-4">
                    <Skeleton className="h-9 w-9 shrink-0 rounded-2xl" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-3 w-24" />
                      <Skeleton className="h-4 w-48" />
                      <Skeleton className="h-3 w-full" />
                    </div>
                  </div>
                ))
              ) : focusTasks.length === 0 ? (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  今日任务已全部完成 🎉
                </p>
              ) : (
                focusTasks.map((task, index) => {
                  const Icon = taskIcon(task.task_type);
                  const href = taskHref(task.task_type);
                  return (
                    <div
                      key={task.id}
                      className="flex gap-4 rounded-2xl border border-border/75 bg-background/70 p-4"
                    >
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                        <Icon size={18} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs font-bold text-primary">Step {index + 1}</span>
                          {task.subject && (
                            <span className="text-xs font-medium text-muted-foreground">
                              {task.subject} · {task.estimated_minutes ?? "—"} 分钟
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-sm font-semibold text-foreground">{task.title}</p>
                        {task.ai_priority_reason && (
                          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                            {task.ai_priority_reason}
                          </p>
                        )}
                      </div>
                      <Link
                        href={href}
                        className={cn(buttonVariants({ variant: "ghost", size: "icon-sm" }), "shrink-0")}
                      >
                        <ArrowRight size={15} />
                      </Link>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>

          <TodayTasks />
          <HeatmapChart />
          <WeeklySummary />
        </div>

        <aside className="space-y-6">
          <Card className="bg-gradient-to-br from-primary/10 via-card to-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Layers3 size={17} className="text-primary" />
                学习路径预览
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                { title: "基础概念", status: "已完成", value: 100 },
                { title: "公式应用", status: "进行中", value: 58 },
                { title: "综合训练", status: "待解锁", value: 12 },
              ].map((item) => (
                <div key={item.title} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-foreground">{item.title}</span>
                    <span className="text-xs text-muted-foreground">{item.status}</span>
                  </div>
                  <Progress value={item.value} className="h-2" />
                </div>
              ))}
              <Link
                href="/tasks"
                className={cn(buttonVariants({ variant: "soft" }), "w-full gap-2")}
              >
                查看完整成长路径
                <ArrowRight size={15} />
              </Link>
            </CardContent>
          </Card>

          <MasteryRing />
          <SubjectProgress />
        </aside>
      </section>
    </div>
  );
}
