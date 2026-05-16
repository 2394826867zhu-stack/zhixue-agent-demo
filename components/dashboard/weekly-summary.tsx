"use client";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sparkles, Loader2 } from "lucide-react";
import { getWeeklyReport } from "@/lib/api";

interface WeeklyReport {
  new_kps?: number;
  flashcard_completion_rate?: number;
  training_avg_score?: number;
  total_minutes?: number;
  ai_advice?: string;
}

function fmt(minutes?: number) {
  if (minutes == null) return "—";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}.${Math.round(m / 6)}h` : `${m}min`;
}

const FALLBACK_ADVICE =
  "本周整体表现良好，物理掌握率偏低（48%），建议下周优先攻克受力分析和动量守恒两个核心知识点。闪卡复习节奏不错，继续保持每日完成率。化学和语文刚开始录入，尽快生成第一批知识点，建立系统框架。";

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

  return (
    <Card className="border-border/60 bg-gradient-to-r from-primary/5 to-primary/0">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-primary" />
          <CardTitle className="text-sm font-semibold">本周学习建议</CardTitle>
          <span className="text-[10px] text-muted-foreground ml-auto">AI生成 · 每周一更新</span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-4 gap-4 mb-4">
          {stats.map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-xl font-bold text-foreground">{s.value}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
        <div className="rounded-lg bg-primary/8 border border-primary/15 px-4 py-3 relative min-h-[56px]">
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 size={14} className="animate-spin" /> AI 建议生成中…
            </div>
          ) : (
            <p className="text-sm text-foreground leading-relaxed">
              {data?.ai_advice ?? FALLBACK_ADVICE}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
