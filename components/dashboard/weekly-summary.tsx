"use client";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getWeeklyReport } from "@/lib/api";

interface WeeklyReport {
  new_kps?: number;
  flashcard_completion_rate?: number;
  training_avg_score?: number;
  total_minutes?: number;
  ai_advice?: string;
  weak_subjects?: string[];
}

function fmt(minutes?: number) {
  if (minutes == null) return "—";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}.${Math.round(m / 6)}h` : `${m}min`;
}

const FALLBACK_ADVICE =
  "本周整体表现良好，建议下周根据薄弱学科做专项训练，闪卡复习节奏不错，继续保持每日完成率。";

export function WeeklySummary() {
  const { data, isLoading } = useQuery<WeeklyReport>({
    queryKey: ["weekly-report", 0],
    queryFn: () => getWeeklyReport(0),
  });

  const stats = [
    { label: "新增知识点", value: data?.new_kps != null ? String(data.new_kps) : "—" },
    { label: "闪卡完成率", value: data?.flashcard_completion_rate != null ? `${Math.round(data.flashcard_completion_rate * 100)}%` : "—" },
    { label: "训练平均分", value: data?.training_avg_score != null ? `${Math.round(data.training_avg_score)}分` : "—" },
    { label: "学习时长", value: fmt(data?.total_minutes) },
  ];

  const weakSubjects = data?.weak_subjects ?? [];

  return (
    <Card className="animate-card-in border-border/60 bg-gradient-to-r from-primary/5 to-primary/0">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-primary" />
          <CardTitle className="text-sm font-semibold">本周学习建议</CardTitle>
          <span className="text-[10px] text-muted-foreground ml-auto">AI生成 · 每周一更新</span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-4">
          {stats.map((s) => (
            <div key={s.label} className="text-center">
              {isLoading ? (
                <>
                  <Skeleton className="mx-auto h-7 w-12" />
                  <Skeleton className="mx-auto mt-2 h-3 w-16" />
                </>
              ) : (
                <>
                  <p className="text-xl font-bold text-foreground">{s.value}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{s.label}</p>
                </>
              )}
            </div>
          ))}
        </div>
        <div className="rounded-lg bg-primary/8 border border-primary/15 px-4 py-3 relative min-h-[56px]">
          {isLoading ? (
            <div className="space-y-2 py-1">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-11/12" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          ) : (
            <p className="text-sm text-foreground leading-relaxed">
              {data?.ai_advice ?? FALLBACK_ADVICE}
            </p>
          )}
        </div>

        {!isLoading && weakSubjects.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {weakSubjects.map((subject) => (
              <Link
                key={subject}
                href={`/training?subject=${encodeURIComponent(subject)}`}
                className="inline-flex items-center gap-1.5 rounded-full border border-destructive/30 bg-destructive/8 px-3 py-1.5 text-xs font-medium text-destructive transition hover:bg-destructive/15"
              >
                → {subject}专项训练
                <ArrowRight size={11} />
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
