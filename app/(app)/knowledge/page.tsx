"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Search, BookOpen, Clock, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { listKPs, getKPStats } from "@/lib/api";

const MASTERY_CONFIG = {
  mastered: { label: "已掌握", color: "bg-green-100 text-green-700", dot: "bg-green-500" },
  reviewing: { label: "复习中", color: "bg-primary/10 text-primary", dot: "bg-primary" },
  learning: { label: "学习中", color: "bg-amber-100 text-amber-700", dot: "bg-amber-500" },
  new: { label: "未开始", color: "bg-slate-100 text-slate-600", dot: "bg-slate-400" },
} as const;

type MasteryKey = keyof typeof MASTERY_CONFIG;

const SUBJECT_COLORS: Record<string, string> = {
  数学: "bg-blue-50 border-blue-200 text-blue-700",
  物理: "bg-purple-50 border-purple-200 text-purple-700",
  化学: "bg-green-50 border-green-200 text-green-700",
  生物: "bg-teal-50 border-teal-200 text-teal-700",
  语文: "bg-red-50 border-red-200 text-red-700",
  英语: "bg-amber-50 border-amber-200 text-amber-700",
};

interface KP {
  id: string;
  name: string;
  subject?: string;
  mastery_status: string;
  stability?: number | null;
  next_review_date?: string | null;
  bloom_level?: string;
  flashcard_count?: number;
}

interface KPStats {
  total: number;
  new: number;
  learning: number;
  reviewing: number;
  mastered: number;
}

export default function KnowledgePage() {
  const [search, setSearch] = useState("");
  const [filterSubject, setFilterSubject] = useState<string | null>(null);
  const [filterMastery, setFilterMastery] = useState<MasteryKey | null>(null);

  const { data: kps = [], isLoading } = useQuery<KP[]>({
    queryKey: ["kps", filterSubject, filterMastery, search],
    queryFn: () =>
      listKPs({
        ...(filterSubject ? { subject: filterSubject } : {}),
        ...(filterMastery ? { mastery_status: filterMastery } : {}),
        ...(search ? { search } : {}),
        page_size: 50,
      }) as Promise<KP[]>,
  });

  const { data: stats } = useQuery<KPStats>({
    queryKey: ["kp-stats"],
    queryFn: () => getKPStats() as Promise<KPStats>,
  });

  const subjects = [...new Set(kps.map((k) => k.subject).filter(Boolean))] as string[];

  const filtered = kps.filter((kp) => {
    if (filterMastery && kp.mastery_status !== filterMastery) return false;
    if (filterSubject && kp.subject !== filterSubject) return false;
    if (search && !kp.name.includes(search)) return false;
    return true;
  });

  const displayStats = stats ?? {
    total: kps.length,
    mastered: kps.filter((k) => k.mastery_status === "mastered").length,
    reviewing: kps.filter((k) => k.mastery_status === "reviewing").length,
    learning: kps.filter((k) => k.mastery_status === "learning").length,
    new: kps.filter((k) => k.mastery_status === "new").length,
  };

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-5 md:space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">知识点</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          共 {displayStats.total} 个知识点
        </p>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(Object.keys(MASTERY_CONFIG) as MasteryKey[]).map((m) => {
          const cfg = MASTERY_CONFIG[m];
          const count = displayStats[m] ?? 0;
          return (
            <button
              key={m}
              onClick={() => setFilterMastery(filterMastery === m ? null : m)}
              className={cn(
                "p-3.5 rounded-xl border text-left transition-all bg-card",
                filterMastery === m
                  ? "ring-2 ring-primary border-primary/30"
                  : "border-border hover:border-primary/30"
              )}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <div className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                <span className="text-xs text-muted-foreground">{cfg.label}</span>
              </div>
              <p className="text-xl font-bold text-foreground">{count}</p>
            </button>
          );
        })}
      </div>

      {/* Filters */}
      <div className="space-y-3">
        <div className="relative max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索知识点…"
            className="w-full pl-8 pr-3 py-2 rounded-lg border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>

        {subjects.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setFilterSubject(null)}
              className={cn(
                "px-3 py-1 rounded-lg text-xs font-medium border transition-colors",
                !filterSubject
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background text-muted-foreground border-border hover:border-primary/50"
              )}
            >
              全部学科
            </button>
            {subjects.map((s) => (
              <button
                key={s}
                onClick={() => setFilterSubject(filterSubject === s ? null : s)}
                className={cn(
                  "px-3 py-1 rounded-lg text-xs font-medium border transition-colors",
                  filterSubject === s
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-background text-muted-foreground border-border hover:border-primary/50"
                )}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <Loader2 size={20} className="animate-spin mr-2" /> 加载中…
        </div>
      )}

      {/* KP List */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((kp) => {
          const mastery = (kp.mastery_status as MasteryKey) in MASTERY_CONFIG
            ? (kp.mastery_status as MasteryKey)
            : "new";
          const m = MASTERY_CONFIG[mastery];
          const sc = kp.subject ? (SUBJECT_COLORS[kp.subject] || "bg-slate-50 border-slate-200 text-slate-700") : "";
          return (
            <Card key={String(kp.id)} className="hover:shadow-md transition-all cursor-pointer">
              <CardContent className="py-3.5 space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  {kp.subject && (
                    <span className={`text-[11px] px-2 py-0.5 rounded-full border font-medium ${sc}`}>
                      {kp.subject}
                    </span>
                  )}
                  <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${m.color}`}>
                    {m.label}
                  </span>
                </div>
                <p className="font-medium text-sm text-foreground">{kp.name}</p>
                <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                  {kp.next_review_date ? (
                    <span className="flex items-center gap-1">
                      <Clock size={10} />
                      {new Date(kp.next_review_date) <= new Date() ? "今天复习" : `复习 ${new Date(kp.next_review_date).toLocaleDateString("zh-CN")}`}
                    </span>
                  ) : mastery !== "new" && kp.stability ? (
                    <span className="flex items-center gap-1">
                      稳定性 {kp.stability.toFixed(1)}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <BookOpen size={10} /> 尚未复习
                    </span>
                  )}
                  {(kp.flashcard_count ?? 0) > 0 && (
                    <span>{kp.flashcard_count} 张闪卡</span>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {!isLoading && filtered.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <BookOpen size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">
            {kps.length === 0 ? "还没有知识点，先生成笔记来创建知识点吧" : "没有匹配的知识点"}
          </p>
        </div>
      )}
    </div>
  );
}
