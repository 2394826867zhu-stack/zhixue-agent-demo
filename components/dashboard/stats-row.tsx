"use client";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Brain, Layers, Clock, AlertCircle } from "lucide-react";
import { getOverview } from "@/lib/api";

interface Overview {
  total_kps?: number;
  due_cards?: number;
  weekly_minutes?: number;
  mistake_count?: number;
  weekly_pomodoros?: number;
  kp_delta_week?: number;
}

function fmt(minutes: number) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}.${Math.round(m / 6)}h` : `${m}min`;
}

export function StatsRow() {
  const { data: overview } = useQuery<Overview>({
    queryKey: ["overview"],
    queryFn: getOverview,
  });

  const stats = [
    {
      label: "知识点总数",
      value: overview?.total_kps ?? "—",
      sub: overview?.kp_delta_week != null ? `较上周 +${overview.kp_delta_week}` : "加载中…",
      icon: Brain,
      color: "text-violet-600",
    },
    {
      label: "今日待复习",
      value: overview?.due_cards ?? "—",
      sub: "闪卡",
      icon: Layers,
      color: "text-amber-600",
    },
    {
      label: "本周学习",
      value: overview?.weekly_minutes != null ? fmt(overview.weekly_minutes) : "—",
      sub: overview?.weekly_pomodoros != null ? `${overview.weekly_pomodoros}个番茄钟` : "",
      icon: Clock,
      color: "text-emerald-600",
    },
    {
      label: "错题待攻克",
      value: overview?.mistake_count ?? "—",
      sub: "题",
      icon: AlertCircle,
      color: "text-rose-600",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
      {stats.map((s) => (
        <Card key={s.label} className="border-border/60">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-muted-foreground font-medium">{s.label}</p>
                <p className="text-2xl font-bold mt-1 text-foreground">{s.value}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{s.sub}</p>
              </div>
              <div className={`p-2 rounded-lg bg-current/8 ${s.color}`}>
                <s.icon size={18} className={s.color} strokeWidth={1.8} />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
