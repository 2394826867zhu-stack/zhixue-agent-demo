"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { TrendingUp, Flame, Clock, Brain, Calendar } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, LineChart, Line, CartesianGrid
} from "recharts";

// Generate 365-day heatmap data
function genHeatmap() {
  const days: { date: string; count: number }[] = [];
  const today = new Date();
  for (let i = 364; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    // Mock: weekdays more active, random bursts
    const isWeekday = d.getDay() !== 0 && d.getDay() !== 6;
    const rand = Math.random();
    let count = 0;
    if (rand > 0.3) count = Math.floor(rand * (isWeekday ? 8 : 5));
    days.push({ date: dateStr, count });
  }
  return days;
}

const HEATMAP = genHeatmap();

function getIntensity(count: number) {
  if (count === 0) return "bg-muted";
  if (count <= 2) return "bg-primary/20";
  if (count <= 4) return "bg-primary/45";
  if (count <= 6) return "bg-primary/70";
  return "bg-primary";
}

const WEEKLY_DATA = [
  { day: "周一", minutes: 45, cards: 12 },
  { day: "周二", minutes: 30, cards: 8 },
  { day: "周三", minutes: 60, cards: 18 },
  { day: "周四", minutes: 25, cards: 6 },
  { day: "周五", minutes: 75, cards: 22 },
  { day: "周六", minutes: 90, cards: 28 },
  { day: "周日", minutes: 50, cards: 14 },
];

const SUBJECT_STATS = [
  { subject: "数学", total: 42, mastered: 28, reviewing: 10, learning: 4, color: "#3b82f6" },
  { subject: "物理", total: 35, mastered: 18, reviewing: 12, learning: 5, color: "#8b5cf6" },
  { subject: "化学", total: 28, mastered: 15, reviewing: 8, learning: 5, color: "#10b981" },
  { subject: "生物", total: 22, mastered: 8, reviewing: 9, learning: 5, color: "#14b8a6" },
  { subject: "英语", total: 38, mastered: 20, reviewing: 14, learning: 4, color: "#f59e0b" },
  { subject: "语文", total: 18, mastered: 6, reviewing: 8, learning: 4, color: "#ef4444" },
];

const MONTH_TREND = [
  { week: "第1周", minutes: 210 },
  { week: "第2周", minutes: 280 },
  { week: "第3周", minutes: 195 },
  { week: "第4周", minutes: 340 },
];

// Group heatmap into weeks (columns)
function groupHeatmapByWeek() {
  const weeks: { date: string; count: number }[][] = [];
  let week: { date: string; count: number }[] = [];
  for (let i = 0; i < HEATMAP.length; i++) {
    const d = new Date(HEATMAP[i].date);
    if (i === 0) {
      // pad start of first week
      for (let j = 0; j < d.getDay(); j++) week.push({ date: "", count: -1 });
    }
    week.push(HEATMAP[i]);
    if (d.getDay() === 6 || i === HEATMAP.length - 1) {
      weeks.push(week);
      week = [];
    }
  }
  return weeks;
}

const WEEKS = groupHeatmapByWeek();

export default function ProgressPage() {
  const totalMastered = SUBJECT_STATS.reduce((a, s) => a + s.mastered, 0);
  const totalKPs = SUBJECT_STATS.reduce((a, s) => a + s.total, 0);
  const masteryRate = Math.round((totalMastered / totalKPs) * 100);
  const weekMinutes = WEEKLY_DATA.reduce((a, d) => a + d.minutes, 0);

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-5 md:space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">学习进度</h1>
        <p className="text-sm text-muted-foreground mt-0.5">全局视角，掌握你的成长轨迹</p>
      </div>

      {/* Key stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        {[
          { label: "本周学习", value: `${weekMinutes}min`, sub: "较上周 +12%", icon: Clock, color: "text-primary" },
          { label: "连续学习", value: "14天", sub: "保持纪录", icon: Flame, color: "text-orange-500" },
          { label: "总掌握率", value: `${masteryRate}%`, sub: `${totalMastered}/${totalKPs} 知识点`, icon: Brain, color: "text-green-600" },
          { label: "本周闪卡", value: "108张", sub: "较上周 +22张", icon: TrendingUp, color: "text-blue-600" },
        ].map(({ label, value, sub, icon: Icon, color }) => (
          <Card key={label} size="sm">
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
          <div className="overflow-x-auto pb-2">
            <div className="flex gap-0.5 min-w-max">
              {WEEKS.map((week, wi) => (
                <div key={wi} className="flex flex-col gap-0.5">
                  {Array.from({ length: 7 }).map((_, di) => {
                    const cell = week[di];
                    if (!cell || cell.count === -1) {
                      return <div key={di} className="w-3 h-3 rounded-sm" />;
                    }
                    return (
                      <div
                        key={di}
                        title={`${cell.date}: ${cell.count} 次学习`}
                        className={`w-3 h-3 rounded-sm ${getIntensity(cell.count)} transition-opacity hover:opacity-80`}
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
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
        {/* Weekly bar chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">本周每日学习时长</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={WEEKLY_DATA} barSize={20}>
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
          </CardContent>
        </Card>

        {/* Month trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">本月周趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={MONTH_TREND}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} unit="min" width={45} />
                <Tooltip
                  contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                  formatter={(v) => [`${v} 分钟`, "学习时长"]}
                />
                <Line type="monotone" dataKey="minutes" stroke="hsl(var(--primary))" strokeWidth={2.5} dot={{ fill: "hsl(var(--primary))", r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Subject breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">各学科知识点掌握情况</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {SUBJECT_STATS.map((s) => {
            const masteryPct = Math.round((s.mastered / s.total) * 100);
            return (
              <div key={s.subject} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ background: s.color }} />
                    <span className="font-medium text-foreground">{s.subject}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="text-green-600 font-medium">掌握 {s.mastered}</span>
                    <span className="text-primary">复习中 {s.reviewing}</span>
                    <span className="text-amber-600">学习中 {s.learning}</span>
                    <span className="font-semibold text-foreground">{masteryPct}%</span>
                  </div>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden flex">
                  <div className="bg-green-500 transition-all" style={{ width: `${(s.mastered / s.total) * 100}%` }} />
                  <div className="bg-primary/70 transition-all" style={{ width: `${(s.reviewing / s.total) * 100}%` }} />
                  <div className="bg-amber-400 transition-all" style={{ width: `${(s.learning / s.total) * 100}%` }} />
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
