"use client";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, Flame, Clock, Brain, Calendar, Loader2 } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import { getOverview, getHeatmap, getSubjects, getWeeklyReport } from "@/lib/api";

const SUBJECT_COLORS: Record<string, string> = {
  数学: "#3b82f6", 物理: "#8b5cf6", 化学: "#10b981",
  生物: "#14b8a6", 英语: "#f59e0b", 语文: "#ef4444",
};
const DAY_NAMES = ["日", "一", "二", "三", "四", "五", "六"];

function getIntensity(minutes: number) {
  if (minutes === 0) return "bg-muted";
  if (minutes < 20) return "bg-primary/20";
  if (minutes < 40) return "bg-primary/45";
  if (minutes < 60) return "bg-primary/70";
  return "bg-primary";
}

function groupHeatmapByWeek(days: { date: string; minutes: number }[]) {
  const weeks: { date: string; minutes: number; empty?: boolean }[][] = [];
  let week: { date: string; minutes: number; empty?: boolean }[] = [];
  for (let i = 0; i < days.length; i++) {
    const d = new Date(days[i].date);
    if (i === 0) {
      for (let j = 0; j < d.getDay(); j++) week.push({ date: "", minutes: -1, empty: true });
    }
    week.push(days[i]);
    if (d.getDay() === 6 || i === days.length - 1) {
      weeks.push(week);
      week = [];
    }
  }
  return weeks;
}

export default function ProgressPage() {
  const { data: overview } = useQuery({
    queryKey: ["progress-overview"],
    queryFn: () => getOverview(),
  });

  const { data: heatmapDays = [], isLoading: heatmapLoading } = useQuery({
    queryKey: ["heatmap", 365],
    queryFn: () => getHeatmap(365) as Promise<{ date: string; minutes: number }[]>,
  });

  const { data: subjects = [] } = useQuery({
    queryKey: ["subjects"],
    queryFn: () => getSubjects() as Promise<{ subject: string; kp_count: number; mastered_count: number; mastery: number; weekly_minutes: number }[]>,
  });

  const { data: weeklyReport } = useQuery({
    queryKey: ["weekly-report", 0],
    queryFn: () => getWeeklyReport(0),
  });

  // Last 7 days from heatmap for weekly bar chart
  const weeklyData = heatmapDays.slice(-7).map((d) => ({
    day: `周${DAY_NAMES[new Date(d.date).getDay()]}`,
    minutes: d.minutes,
  }));

  const weeks = groupHeatmapByWeek(heatmapDays);

  const weekMinutes = weeklyReport?.total_minutes ?? overview?.weekly_minutes ?? 0;

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-5 md:space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">学习进度</h1>
        <p className="text-sm text-muted-foreground mt-0.5">全局视角，掌握你的成长轨迹</p>
      </div>

      {/* Key stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        {[
          {
            label: "本周学习",
            value: weekMinutes ? `${weekMinutes}min` : "—",
            sub: `${weeklyReport?.pomodoro_count ?? 0} 个番茄钟`,
            icon: Clock, color: "text-primary",
          },
          {
            label: "连续学习",
            value: "—",
            sub: "暂无连续数据",
            icon: Flame, color: "text-orange-500",
          },
          {
            label: "知识点总数",
            value: overview ? `${overview.total_kps}` : "—",
            sub: overview ? `本周+${overview.kp_delta_week}` : "加载中",
            icon: Brain, color: "text-green-600",
          },
          {
            label: "待复习闪卡",
            value: overview ? `${overview.due_cards}` : "—",
            sub: overview ? `错题 ${overview.mistake_count} 道` : "加载中",
            icon: TrendingUp, color: "text-blue-600",
          },
        ].map(({ label, value, sub, icon: Icon, color }) => (
          <Card key={label}>
            <CardContent className="py-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>
                </div>
                <Icon size={18} className={`${color} opacity-70 mt-0.5`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Heatmap */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Calendar size={16} className="text-primary" /> 学习热力图（近365天）
          </CardTitle>
        </CardHeader>
        <CardContent>
          {heatmapLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground py-6">
              <Loader2 size={15} className="animate-spin" /> 加载中…
            </div>
          ) : (
            <>
              <div className="overflow-x-auto pb-2">
                <div className="flex gap-0.5 min-w-max">
                  {weeks.map((week, wi) => (
                    <div key={wi} className="flex flex-col gap-0.5">
                      {Array.from({ length: 7 }).map((_, di) => {
                        const cell = week[di];
                        if (!cell || cell.empty || cell.minutes === -1) {
                          return <div key={di} className="w-3 h-3 rounded-sm" />;
                        }
                        return (
                          <div
                            key={di}
                            title={`${cell.date}: ${cell.minutes} 分钟`}
                            className={`w-3 h-3 rounded-sm ${getIntensity(cell.minutes)} transition-opacity hover:opacity-80 cursor-default`}
                          />
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-1.5 mt-3 text-xs text-muted-foreground">
                <span>少</span>
                {["bg-muted", "bg-primary/20", "bg-primary/45", "bg-primary/70", "bg-primary"].map((c) => (
                  <div key={c} className={`w-3 h-3 rounded-sm ${c}`} />
                ))}
                <span>多</span>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Weekly bar + AI advice */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">本周每日学习时长</CardTitle>
          </CardHeader>
          <CardContent>
            {weeklyData.length > 0 ? (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={weeklyData} barSize={20}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} unit="min" width={40} />
                  <Tooltip
                    contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                    formatter={(v) => [`${v} 分钟`, "学习时长"]}
                  />
                  <Bar dataKey="minutes" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-44 text-muted-foreground text-sm">
                暂无数据
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">AI 本周建议</CardTitle>
          </CardHeader>
          <CardContent>
            {weeklyReport ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 rounded-lg bg-muted/60 space-y-0.5">
                    <p className="text-muted-foreground">新增知识点</p>
                    <p className="font-semibold text-foreground">{weeklyReport.new_kps} 个</p>
                  </div>
                  <div className="p-2 rounded-lg bg-muted/60 space-y-0.5">
                    <p className="text-muted-foreground">训练均分</p>
                    <p className="font-semibold text-foreground">
                      {weeklyReport.training_avg_score != null ? `${Math.round(weeklyReport.training_avg_score)}分` : "—"}
                    </p>
                  </div>
                  <div className="p-2 rounded-lg bg-muted/60 space-y-0.5">
                    <p className="text-muted-foreground">闪卡完成率</p>
                    <p className="font-semibold text-foreground">{Math.round((weeklyReport.flashcard_completion_rate ?? 0) * 100)}%</p>
                  </div>
                  <div className="p-2 rounded-lg bg-muted/60 space-y-0.5">
                    <p className="text-muted-foreground">新增错题</p>
                    <p className="font-semibold text-foreground">{weeklyReport.wrong_count} 道</p>
                  </div>
                </div>
                <p className="text-sm text-foreground leading-relaxed">{weeklyReport.ai_advice}</p>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-muted-foreground py-6">
                <Loader2 size={15} className="animate-spin" /> 加载中…
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Subject breakdown */}
      {subjects.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">各学科知识点掌握情况</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {subjects.map((s) => {
              const color = SUBJECT_COLORS[s.subject] ?? "#6b7280";
              const masteryPct = Math.round(s.mastery);
              return (
                <div key={s.subject} className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                      <span className="font-medium text-foreground">{s.subject}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="text-green-600 font-medium">掌握 {s.mastered_count}</span>
                      <span className="text-muted-foreground">共 {s.kp_count}</span>
                      <span className="font-semibold text-foreground">{masteryPct}%</span>
                    </div>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${masteryPct}%`, background: color }}
                    />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
