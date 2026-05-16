"use client";
import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search, BookOpen, Clock, RotateCcw } from "lucide-react";

const MASTERY_CONFIG = {
  mastered: { label: "已掌握", color: "bg-green-100 text-green-700", dot: "bg-green-500" },
  reviewing: { label: "复习中", color: "bg-primary/10 text-primary", dot: "bg-primary" },
  learning: { label: "学习中", color: "bg-amber-100 text-amber-700", dot: "bg-amber-500" },
  new: { label: "未开始", color: "bg-slate-100 text-slate-600", dot: "bg-slate-400" },
} as const;

type Mastery = keyof typeof MASTERY_CONFIG;

const MOCK_KPS = [
  { id: "1", name: "等差数列求和", subject: "数学", mastery: "mastered" as Mastery, next_review: "3天后", stability: 12.4 },
  { id: "2", name: "牛顿第二定律", subject: "物理", mastery: "reviewing" as Mastery, next_review: "今天", stability: 2.1 },
  { id: "3", name: "细胞有丝分裂", subject: "生物", mastery: "learning" as Mastery, next_review: "明天", stability: 0.8 },
  { id: "4", name: "氧化还原反应", subject: "化学", mastery: "mastered" as Mastery, next_review: "7天后", stability: 18.2 },
  { id: "5", name: "函数的极限", subject: "数学", mastery: "learning" as Mastery, next_review: "今天", stability: 1.2 },
  { id: "6", name: "阿伏伽德罗定律", subject: "化学", mastery: "reviewing" as Mastery, next_review: "明天", stability: 3.6 },
  { id: "7", name: "基因的分离定律", subject: "生物", mastery: "new" as Mastery, next_review: "—", stability: 0 },
  { id: "8", name: "万有引力定律", subject: "物理", mastery: "mastered" as Mastery, next_review: "5天后", stability: 9.8 },
  { id: "9", name: "定语从句", subject: "英语", mastery: "reviewing" as Mastery, next_review: "今天", stability: 2.9 },
  { id: "10", name: "文言文句式", subject: "语文", mastery: "learning" as Mastery, next_review: "明天", stability: 1.5 },
  { id: "11", name: "动量守恒定律", subject: "物理", mastery: "new" as Mastery, next_review: "—", stability: 0 },
  { id: "12", name: "等比数列", subject: "数学", mastery: "mastered" as Mastery, next_review: "10天后", stability: 22.1 },
];

const SUBJECT_COLORS: Record<string, string> = {
  数学: "bg-blue-50 border-blue-200 text-blue-700",
  物理: "bg-purple-50 border-purple-200 text-purple-700",
  化学: "bg-green-50 border-green-200 text-green-700",
  生物: "bg-teal-50 border-teal-200 text-teal-700",
  语文: "bg-red-50 border-red-200 text-red-700",
  英语: "bg-amber-50 border-amber-200 text-amber-700",
};

export default function KnowledgePage() {
  const [search, setSearch] = useState("");
  const [filterSubject, setFilterSubject] = useState<string | null>(null);
  const [filterMastery, setFilterMastery] = useState<Mastery | null>(null);

  const subjects = [...new Set(MOCK_KPS.map((k) => k.subject))];

  const filtered = MOCK_KPS.filter((kp) => {
    if (filterSubject && kp.subject !== filterSubject) return false;
    if (filterMastery && kp.mastery !== filterMastery) return false;
    if (search && !kp.name.includes(search)) return false;
    return true;
  });

  const stats = {
    total: MOCK_KPS.length,
    mastered: MOCK_KPS.filter((k) => k.mastery === "mastered").length,
    reviewing: MOCK_KPS.filter((k) => k.mastery === "reviewing").length,
    learning: MOCK_KPS.filter((k) => k.mastery === "learning").length,
    new: MOCK_KPS.filter((k) => k.mastery === "new").length,
  };

  const masteryPct = Math.round((stats.mastered / stats.total) * 100);
  const R_kp = 44;
  const circ_kp = 2 * Math.PI * R_kp;
  const ringOffset_kp = circ_kp * (1 - masteryPct / 100);

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-6 md:space-y-8">
      {/* Header with mastery ring */}
      <div className="flex items-center gap-6">
        <div className="relative shrink-0">
          <svg width="100" height="100" className="-rotate-90">
            <circle cx="50" cy="50" r={R_kp} fill="none" stroke="hsl(var(--muted))" strokeWidth="8" />
            <circle
              cx="50" cy="50" r={R_kp} fill="none"
              stroke="hsl(142 76% 36%)"
              strokeWidth="8"
              strokeDasharray={circ_kp}
              strokeDashoffset={ringOffset_kp}
              strokeLinecap="round"
              className="transition-all duration-700"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-bold text-foreground leading-none">{masteryPct}%</span>
            <span className="text-[10px] text-muted-foreground mt-0.5">掌握</span>
          </div>
        </div>
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-foreground tracking-tight">知识点</h1>
          <p className="text-sm text-muted-foreground mt-1">共 {stats.total} 个 · 已掌握 {stats.mastered} 个</p>
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(Object.keys(MASTERY_CONFIG) as Mastery[]).map((m) => {
          const cfg = MASTERY_CONFIG[m];
          return (
            <button
              key={m}
              onClick={() => setFilterMastery(filterMastery === m ? null : m)}
              className={`p-4 rounded-2xl border text-left transition-all hover:shadow-sm ${
                filterMastery === m ? "ring-2 ring-primary border-primary/30 shadow-sm" : "border-border hover:border-primary/30"
              } bg-card`}
            >
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-2.5 h-2.5 rounded-full ${cfg.dot}`} />
                <span className="text-xs text-muted-foreground">{cfg.label}</span>
              </div>
              <p className="text-2xl font-bold text-foreground">{stats[m]}</p>
            </button>
          );
        })}
      </div>

      {/* Filters */}
      <div className="space-y-3">
        {/* Search */}
        <div className="relative max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索知识点…"
            className="w-full pl-8 pr-3 py-2 rounded-lg border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>

        {/* Subject filter */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setFilterSubject(null)}
            className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${
              !filterSubject ? "bg-primary text-primary-foreground border-primary" : "bg-background text-muted-foreground border-border hover:border-primary/50"
            }`}
          >
            全部学科
          </button>
          {subjects.map((s) => (
            <button
              key={s}
              onClick={() => setFilterSubject(filterSubject === s ? null : s)}
              className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${
                filterSubject === s ? "bg-primary text-primary-foreground border-primary" : "bg-background text-muted-foreground border-border hover:border-primary/50"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* KP List */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((kp) => {
          const m = MASTERY_CONFIG[kp.mastery];
          const sc = SUBJECT_COLORS[kp.subject] || "bg-slate-50 border-slate-200 text-slate-700";
          return (
            <Card key={kp.id} size="sm" className="hover:shadow-md transition-all cursor-pointer group focus-within:ring-2 focus-within:ring-primary/40">
              <CardContent className="py-3.5 space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <span className={`text-[11px] px-2 py-0.5 rounded-full border font-medium ${sc}`}>
                    {kp.subject}
                  </span>
                  <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${m.color}`}>
                    {m.label}
                  </span>
                </div>
                <p className="font-medium text-sm text-foreground">{kp.name}</p>
                <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                  {kp.mastery !== "new" ? (
                    <>
                      <span className="flex items-center gap-1"><Clock size={10} /> {kp.next_review}</span>
                      <span className="flex items-center gap-1"><RotateCcw size={10} /> 稳定性 {kp.stability.toFixed(1)}</span>
                    </>
                  ) : (
                    <span className="flex items-center gap-1"><BookOpen size={10} /> 尚未学习</span>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <BookOpen size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">没有匹配的知识点</p>
        </div>
      )}
    </div>
  );
}
