"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Award,
  BookOpen,
  Brain,
  CheckCircle2,
  Clock,
  Flame,
  MessageCircle,
  PenLine,
  Send,
  Sparkles,
  Target,
  Trophy,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getAchievements,
  getProfileInsights,
  listReflections,
  saveReflection,
  type Achievement,
  type ProfileInsights,
  type Reflection,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function minutesToHours(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

function AchievementCard({ item }: { item: Achievement }) {
  return (
    <Card
      size="sm"
      className={cn(
        "tap-feedback border-border/70",
        item.earned ? "bg-gradient-to-br from-primary/10 via-card to-card" : "bg-card/82 opacity-80"
      )}
    >
      <CardContent className="space-y-3 py-1">
        <div className="flex items-start justify-between gap-3">
          <div className={cn("flex h-11 w-11 items-center justify-center rounded-2xl text-sm font-bold", item.earned ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>
            {item.icon}
          </div>
          {item.earned ? (
            <CheckCircle2 size={18} className="text-primary" />
          ) : (
            <span className="text-xs font-semibold text-muted-foreground">{Math.round(item.progress_pct)}%</span>
          )}
        </div>
        <div>
          <h3 className="text-sm font-semibold text-foreground">{item.title}</h3>
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">{item.description}</p>
        </div>
        <div>
          <Progress value={item.progress_pct} className="h-1.5" />
          <p className="mt-1.5 text-[11px] text-muted-foreground">
            {item.progress} / {item.target}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const [reflection, setReflection] = useState("");

  const { data: insights, isLoading: insightsLoading } = useQuery<ProfileInsights>({
    queryKey: ["profile-insights"],
    queryFn: getProfileInsights,
  });

  const { data: achievements = [], isLoading: achievementsLoading } = useQuery<Achievement[]>({
    queryKey: ["profile-achievements"],
    queryFn: getAchievements,
  });

  const { data: reflections } = useQuery<{ items: Reflection[]; total: number; page: number; page_size: number }>({
    queryKey: ["profile-reflections"],
    queryFn: () => listReflections(1, 10),
  });

  const reflectionMutation = useMutation({
    mutationFn: () => saveReflection({ content: reflection }),
    onSuccess: () => {
      setReflection("");
      queryClient.invalidateQueries({ queryKey: ["profile-reflections"] });
    },
  });

  const stats = useMemo(() => {
    if (!insights) return [];
    return [
      {
        label: "连续学习",
        value: `${insights.streak_days}`,
        unit: "天",
        icon: Flame,
        tone: "text-amber-600",
      },
      {
        label: "累计专注",
        value: minutesToHours(insights.total_focus_minutes),
        unit: "",
        icon: Clock,
        tone: "text-sky-600",
      },
      {
        label: "掌握知识点",
        value: `${insights.mastered_kps}`,
        unit: `/${insights.total_kps}`,
        icon: Brain,
        tone: "text-primary",
      },
      {
        label: "训练均分",
        value: insights.training_avg_score != null ? `${Math.round(insights.training_avg_score)}` : "—",
        unit: "分",
        icon: Target,
        tone: "text-violet-600",
      },
    ];
  }, [insights]);

  const earned = achievements.filter((item) => item.earned);

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
      <section className="overflow-hidden rounded-[1.75rem] border border-border/75 bg-card/92 shadow-[var(--shadow-card)]">
        <div className="grid gap-6 p-5 lg:grid-cols-[1.25fr_0.75fr] md:p-7">
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="bg-primary/10 text-primary">
                个人成长中心
              </Badge>
              <Badge variant="outline">{insights?.achievements_earned ?? "—"} / {insights?.achievements_total ?? "—"} 成就</Badge>
            </div>
            <div className="max-w-2xl">
              <h1 className="text-2xl font-bold tracking-normal text-foreground md:text-3xl">
                看到自己的持续进步，而不是只看到待办
              </h1>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground md:text-base">
                知曜会把学习时长、知识点、复习、训练和深度思考沉淀成可追踪的成长记录。
              </p>
            </div>
          </div>

          <div className="rounded-3xl border border-primary/18 bg-gradient-to-br from-primary/12 via-card to-card p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-foreground">成就进度</p>
                <p className="mt-1 text-xs text-muted-foreground">已点亮 {earned.length} 个徽章</p>
              </div>
              <div className="rounded-2xl bg-primary/10 p-2 text-primary">
                <Trophy size={20} />
              </div>
            </div>
            <div className="mt-6">
              <div className="flex items-end justify-between">
                <p className="text-4xl font-bold text-foreground">
                  {insights ? Math.round((insights.achievements_earned / insights.achievements_total) * 100) : 0}%
                </p>
                <p className="text-xs font-medium text-muted-foreground">低压力积累</p>
              </div>
              <Progress
                value={insights ? (insights.achievements_earned / insights.achievements_total) * 100 : 0}
                className="mt-3 h-2.5"
              />
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
        {insightsLoading
          ? Array.from({ length: 4 }).map((_, index) => (
              <Card key={index} size="sm">
                <CardContent className="py-1">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="mt-3 h-8 w-16" />
                  <Skeleton className="mt-2 h-3 w-24" />
                </CardContent>
              </Card>
            ))
          : stats.map(({ label, value, unit, icon: Icon, tone }) => (
              <Card key={label} size="sm" className="animate-card-in">
                <CardContent className="py-1">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground">{label}</p>
                      <p className="mt-1 text-2xl font-bold text-foreground">
                        {value}
                        {unit && <span className="ml-1 text-sm font-semibold text-muted-foreground">{unit}</span>}
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
        <main className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Award size={17} className="text-primary" />
                    成就徽章
                  </CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">每个徽章都是一次真实行动的记录。</p>
                </div>
                <Badge variant="secondary">{earned.length} 已点亮</Badge>
              </div>
            </CardHeader>
            <CardContent>
              {achievementsLoading ? (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <Skeleton key={index} className="h-36 rounded-2xl" />
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                  {achievements.map((item) => (
                    <AchievementCard key={item.id} item={item} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PenLine size={17} className="text-primary" />
                本周复盘
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <textarea
                value={reflection}
                onChange={(e) => setReflection(e.target.value)}
                placeholder="写下这周最有效的一件事、一个卡住的点，以及下周想保持的节奏。"
                className="min-h-[130px] w-full resize-none rounded-2xl border border-border bg-background/80 px-4 py-3 text-sm leading-relaxed text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-4 focus:ring-primary/15"
              />
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-muted-foreground">同一周重复提交会覆盖上一版，方便持续打磨。</p>
                <Button
                  className="gap-2"
                  disabled={!reflection.trim() || reflectionMutation.isPending}
                  onClick={() => reflectionMutation.mutate()}
                >
                  <Send size={15} />
                  保存复盘
                </Button>
              </div>
            </CardContent>
          </Card>
        </main>

        <aside className="space-y-5">
          <Card className="border-primary/18 bg-gradient-to-br from-primary/10 via-card to-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles size={17} className="text-primary" />
                成长摘要
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                { label: "笔记资产", value: insights?.total_notes ?? "—", icon: BookOpen },
                { label: "闪卡复习", value: insights?.total_flashcard_reviews ?? "—", icon: CheckCircle2 },
                { label: "AI 引导", value: insights?.total_guidance_sessions ?? "—", icon: MessageCircle },
              ].map(({ label, value, icon: Icon }) => (
                <div key={label} className="flex items-center justify-between rounded-2xl border border-border/70 bg-card/70 p-3">
                  <div className="flex items-center gap-2">
                    <div className="rounded-xl bg-primary/10 p-2 text-primary">
                      <Icon size={15} />
                    </div>
                    <span className="text-sm font-semibold text-foreground">{label}</span>
                  </div>
                  <span className="text-sm font-bold text-foreground">{value}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">历史复盘</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {(reflections?.items ?? []).length > 0 ? (
                reflections!.items.map((item) => (
                  <div key={item.id} className="rounded-2xl border border-border/70 bg-background/70 p-3">
                    <p className="text-xs font-semibold text-primary">
                      {item.week_start} 至 {item.week_end}
                    </p>
                    <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-muted-foreground">{item.content}</p>
                  </div>
                ))
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">还没有复盘记录</p>
              )}
            </CardContent>
          </Card>
        </aside>
      </section>
    </div>
  );
}

