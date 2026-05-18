"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import {
  Search, BookOpen, Clock, Loader2, Sparkles, Brain,
  ChevronDown, ChevronRight, Layers, LibraryBig,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  generateNoteFromChapter,
  getChapterKPs,
  getCurriculumChapters,
  listKPs,
  getKPStats,
} from "@/lib/api";

const MASTERY_CONFIG = {
  mastered: { label: "已掌握", color: "bg-green-100 text-green-700", dot: "bg-green-500", bar: "bg-green-500" },
  reviewing: { label: "复习中", color: "bg-primary/10 text-primary", dot: "bg-primary", bar: "bg-primary" },
  learning:  { label: "学习中", color: "bg-amber-100 text-amber-700", dot: "bg-amber-500", bar: "bg-amber-400" },
  new:       { label: "未开始", color: "bg-slate-100 text-slate-600", dot: "bg-slate-400", bar: "bg-slate-300" },
} as const;

type MasteryKey = keyof typeof MASTERY_CONFIG;

const SUBJECT_COLORS: Record<string, string> = {
  数学: "bg-blue-50 border-blue-200 text-blue-700",
  物理: "bg-purple-50 border-purple-200 text-purple-700",
  化学: "bg-green-50 border-green-200 text-green-700",
  生物: "bg-teal-50 border-teal-200 text-teal-700",
  语文: "bg-red-50 border-red-200 text-red-700",
  英语: "bg-amber-50 border-amber-200 text-amber-700",
  历史: "bg-orange-50 border-orange-200 text-orange-700",
  地理: "bg-cyan-50 border-cyan-200 text-cyan-700",
  政治: "bg-rose-50 border-rose-200 text-rose-700",
};

const CURRICULUM_SUBJECTS = ["数学", "物理", "化学", "生物", "英语"];
const GRADE_OPTIONS = [
  { value: 1, label: "高一" },
  { value: 2, label: "高二" },
  { value: 3, label: "高三" },
];

interface KP {
  id: string;
  name: string;
  subject?: string;
  mastery_status: string;
  stability?: number | null;
  next_review_date?: string | null;
  bloom_level?: string;
  flashcard_count?: number;
  content?: string | null;
}

interface KPStats {
  total: number;
  new: number;
  learning: number;
  reviewing: number;
  mastered: number;
  by_subject?: Record<string, number>;
}

interface CurriculumLesson {
  id: string;
  subject: string;
  grade_type: string;
  grade_year: number;
  semester: number;
  chapter_index: number;
  chapter_title: string;
  lesson_index: number;
  lesson_title: string;
  textbook_version: string;
  is_key: boolean;
  kp_count: number;
}

interface CurriculumChapter {
  chapter_index: number;
  chapter_title: string;
  lessons: CurriculumLesson[];
}

export default function KnowledgePage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [filterSubject, setFilterSubject] = useState<string | null>(null);
  const [filterMastery, setFilterMastery] = useState<MasteryKey | null>(null);
  const [view, setView] = useState<"all" | "curriculum">("all");
  const [curriculumSubject, setCurriculumSubject] = useState("数学");
  const [curriculumGrade, setCurriculumGrade] = useState(2);
  const [selectedLesson, setSelectedLesson] = useState<CurriculumLesson | null>(null);
  const [expandedSubjects, setExpandedSubjects] = useState<Set<string>>(new Set());

  const { data: kps = [], isLoading } = useQuery<KP[]>({
    queryKey: ["kps"],
    queryFn: () => listKPs({ page_size: 200 }) as Promise<KP[]>,
  });

  const { data: stats } = useQuery<KPStats>({
    queryKey: ["kp-stats"],
    queryFn: () => getKPStats() as Promise<KPStats>,
  });

  const { data: curriculum = [], isLoading: curriculumLoading } = useQuery<CurriculumChapter[]>({
    queryKey: ["curriculum", "senior_high", curriculumGrade, curriculumSubject],
    queryFn: () => getCurriculumChapters({ grade_type: "senior_high", grade_year: curriculumGrade, subject: curriculumSubject }) as Promise<CurriculumChapter[]>,
  });

  const { data: lessonKPs = [], isLoading: lessonKPsLoading } = useQuery<KP[]>({
    queryKey: ["chapter-kps", selectedLesson?.id],
    queryFn: () => getChapterKPs(selectedLesson!.id) as Promise<KP[]>,
    enabled: !!selectedLesson,
  });

  const generateChapterMut = useMutation({
    mutationFn: (chapterId: string) => generateNoteFromChapter(chapterId) as Promise<{ note_id: string; status: string }>,
    onSuccess: (data) => router.push(`/notes/${data.note_id}`),
  });

  const allSubjects = [...new Set(kps.map((k) => k.subject).filter(Boolean))] as string[];

  // Per-subject mastery rate
  const subjectStats = allSubjects.map((s) => {
    const sKPs = kps.filter((k) => k.subject === s);
    const mastered = sKPs.filter((k) => k.mastery_status === "mastered" || k.mastery_status === "reviewing").length;
    return { subject: s, total: sKPs.length, mastered, pct: sKPs.length > 0 ? Math.round((mastered / sKPs.length) * 100) : 0 };
  });

  const filtered = kps.filter((kp) => {
    if (filterMastery && kp.mastery_status !== filterMastery) return false;
    if (filterSubject && kp.subject !== filterSubject) return false;
    if (search && !kp.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });
  const visibleKPs = view === "curriculum" && selectedLesson ? lessonKPs : filtered;

  const displayStats = stats ?? {
    total: kps.length,
    mastered: kps.filter((k) => k.mastery_status === "mastered").length,
    reviewing: kps.filter((k) => k.mastery_status === "reviewing").length,
    learning: kps.filter((k) => k.mastery_status === "learning").length,
    new: kps.filter((k) => k.mastery_status === "new").length,
  };

  function toggleSubject(s: string) {
    setExpandedSubjects((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s); else next.add(s);
      return next;
    });
  }

  return (
    <div className="flex min-h-[calc(100vh-4rem)] max-w-6xl mx-auto">
      {/* ── Left Sidebar ── */}
      <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border/60 bg-card/60 py-6 px-4 gap-6 sticky top-0 h-screen overflow-y-auto">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Brain size={16} className="text-primary" />
            <h2 className="text-sm font-bold text-foreground">知识库</h2>
          </div>
          <p className="text-xs text-muted-foreground">{displayStats.total} 个知识点</p>
        </div>

        <div className="grid grid-cols-2 gap-1 rounded-xl bg-muted p-1">
          {[
            { key: "all", label: "全部" },
            { key: "curriculum", label: "课程" },
          ].map((item) => (
            <button
              key={item.key}
              onClick={() => setView(item.key as "all" | "curriculum")}
              className={cn(
                "rounded-lg px-2 py-1.5 text-xs font-semibold transition-colors",
                view === item.key ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {item.label}
            </button>
          ))}
        </div>

        {view === "all" ? (
          <>
          {/* Mastery filter */}
          <div className="space-y-1.5">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">按掌握度</p>
          <button
            onClick={() => setFilterMastery(null)}
            className={cn(
              "w-full flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
              !filterMastery ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted"
            )}
          >
            <div className="w-2 h-2 rounded-full bg-primary/40" />
            全部 ({displayStats.total})
          </button>
          {(Object.keys(MASTERY_CONFIG) as MasteryKey[]).map((m) => {
            const cfg = MASTERY_CONFIG[m];
            const count = displayStats[m] ?? 0;
            return (
              <button
                key={m}
                onClick={() => setFilterMastery(filterMastery === m ? null : m)}
                className={cn(
                  "w-full flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                  filterMastery === m ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted"
                )}
              >
                <div className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                {cfg.label} ({count})
              </button>
            );
          })}
          </div>

          {/* Subject accordion */}
          {allSubjects.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">按学科</p>
            <button
              onClick={() => setFilterSubject(null)}
              className={cn(
                "w-full flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                !filterSubject ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted"
              )}
            >
              全部学科
            </button>
            {subjectStats.map(({ subject, total, pct }) => {
              const isActive = filterSubject === subject;
              const isExpanded = expandedSubjects.has(subject);
              return (
                <div key={subject}>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setFilterSubject(isActive ? null : subject)}
                      className={cn(
                        "flex-1 flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors text-left",
                        isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted"
                      )}
                    >
                      <span className="flex-1 truncate">{subject}</span>
                      <span className="shrink-0 text-[10px]">{total}</span>
                    </button>
                    <button
                      onClick={() => toggleSubject(subject)}
                      className="p-0.5 text-muted-foreground hover:text-foreground"
                    >
                      {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                    </button>
                  </div>
                  {/* Mini mastery bar */}
                  <div className="mx-2.5 mt-0.5 h-1 rounded-full bg-muted overflow-hidden">
                    <div className="h-full rounded-full bg-primary/60" style={{ width: `${pct}%` }} />
                  </div>
                  {/* Expanded KP list */}
                  {isExpanded && (
                    <div className="ml-4 mt-1 space-y-0.5">
                      {kps.filter((k) => k.subject === subject).slice(0, 8).map((kp) => {
                        const m = MASTERY_CONFIG[(kp.mastery_status as MasteryKey) in MASTERY_CONFIG ? (kp.mastery_status as MasteryKey) : "new"];
                        return (
                          <Link
                            key={kp.id}
                            href={`/knowledge/${kp.id}`}
                            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                          >
                            <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${m.dot}`} />
                            <span className="truncate">{kp.name}</span>
                          </Link>
                        );
                      })}
                      {kps.filter((k) => k.subject === subject).length > 8 && (
                        <button
                          onClick={() => setFilterSubject(subject)}
                          className="pl-4 text-[11px] text-primary hover:underline"
                        >
                          查看全部 {kps.filter((k) => k.subject === subject).length} 个 →
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          )}
          </>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <LibraryBig size={14} className="text-primary" />
              <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                {GRADE_OPTIONS.find((g) => g.value === curriculumGrade)?.label} · {curriculumSubject}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-1 rounded-lg bg-muted p-1">
              {GRADE_OPTIONS.map((grade) => (
                <button
                  key={grade.value}
                  onClick={() => {
                    setCurriculumGrade(grade.value);
                    setSelectedLesson(null);
                  }}
                  className={cn(
                    "rounded-md px-1.5 py-1 text-[11px] font-semibold transition-colors",
                    curriculumGrade === grade.value ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"
                  )}
                >
                  {grade.label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-1">
              {CURRICULUM_SUBJECTS.map((subject) => (
                <button
                  key={subject}
                  onClick={() => {
                    setCurriculumSubject(subject);
                    setSelectedLesson(null);
                  }}
                  className={cn(
                    "rounded-md border px-2 py-1 text-[11px] font-semibold transition-colors",
                    curriculumSubject === subject
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-background text-muted-foreground"
                  )}
                >
                  {subject}
                </button>
              ))}
            </div>
            {curriculumLoading ? (
              <div className="flex items-center gap-2 px-2 py-3 text-xs text-muted-foreground">
                <Loader2 size={13} className="animate-spin" /> 加载课程目录…
              </div>
            ) : (
              curriculum.map((chapter) => (
                <div key={`${chapter.chapter_index}-${chapter.chapter_title}`} className="space-y-1">
                  <p className="px-2 text-xs font-semibold text-foreground">
                    第{chapter.chapter_index}章 {chapter.chapter_title}
                  </p>
                  <div className="space-y-0.5">
                    {chapter.lessons.map((lesson) => {
                      const active = selectedLesson?.id === lesson.id;
                      return (
                        <button
                          key={lesson.id}
                          onClick={() => {
                            setSelectedLesson(lesson);
                            setView("curriculum");
                          }}
                          className={cn(
                            "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[11px] transition-colors",
                            active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                          )}
                        >
                          <span className="shrink-0 font-mono">{lesson.chapter_index}.{lesson.lesson_index}</span>
                          <span className="min-w-0 flex-1 truncate">{lesson.lesson_title}</span>
                          <span className={cn(
                            "shrink-0 rounded-full px-1.5 py-0.5 text-[10px]",
                            lesson.kp_count > 0 ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                          )}>
                            {lesson.kp_count > 0 ? `${lesson.kp_count}` : "生成"}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </aside>

      {/* ── Main Content ── */}
      <main className="flex-1 p-4 md:p-6 space-y-5 overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold text-foreground">
              {view === "curriculum" && selectedLesson
                ? selectedLesson.lesson_title
                : filterSubject ? filterSubject : filterMastery ? MASTERY_CONFIG[filterMastery].label : "全部知识点"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {view === "curriculum" && selectedLesson
                ? `第${selectedLesson.chapter_index}.${selectedLesson.lesson_index}课时 · ${visibleKPs.length} 个知识点`
                : `${filtered.length} 个知识点`}
            </p>
          </div>
          <Link
            href="/notes?mode=generate"
            className="flex items-center gap-1.5 rounded-xl bg-primary px-3.5 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Sparkles size={14} /> 生成笔记
          </Link>
        </div>

        {/* Mobile subject pills */}
        <div className="flex md:hidden flex-wrap gap-2">
          <button
            onClick={() => setFilterSubject(null)}
            className={cn("px-3 py-1 rounded-lg text-xs font-medium border transition-colors",
              !filterSubject ? "bg-primary text-primary-foreground border-primary" : "bg-background text-muted-foreground border-border")}
          >全部</button>
          {allSubjects.map((s) => (
            <button key={s}
              onClick={() => setFilterSubject(filterSubject === s ? null : s)}
              className={cn("px-3 py-1 rounded-lg text-xs font-medium border transition-colors",
                filterSubject === s ? "bg-primary text-primary-foreground border-primary" : "bg-background text-muted-foreground border-border")}
            >{s}</button>
          ))}
        </div>

        {/* Mastery stats (mobile) */}
        <div className="flex md:hidden flex-wrap gap-2">
          {(Object.keys(MASTERY_CONFIG) as MasteryKey[]).map((m) => {
            const cfg = MASTERY_CONFIG[m];
            return (
              <button key={m}
                onClick={() => setFilterMastery(filterMastery === m ? null : m)}
                className={cn("flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-all",
                  filterMastery === m ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground")}
              >
                <div className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                {cfg.label} {displayStats[m]}
              </button>
            );
          })}
        </div>

        {view === "curriculum" && selectedLesson && visibleKPs.length === 0 && !lessonKPsLoading && (
          <Card className="border-dashed bg-primary/4">
            <CardContent className="flex flex-col gap-3 py-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-foreground">这个课时还没有知识点</p>
                <p className="mt-1 text-xs text-muted-foreground">可以先让 AI 生成一篇课程笔记，完成后会沉淀到知识库。</p>
              </div>
              <button
                onClick={() => generateChapterMut.mutate(selectedLesson.id)}
                disabled={generateChapterMut.isPending}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-70"
              >
                {generateChapterMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                生成课程笔记
              </button>
            </CardContent>
          </Card>
        )}

        {/* Search */}
        {view === "all" && (
        <div className="relative max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索知识点…"
            className="w-full pl-8 pr-3 py-2 rounded-lg border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>
        )}

        {(isLoading || lessonKPsLoading) && (
          <div className="flex items-center justify-center py-16 text-muted-foreground">
            <Loader2 size={20} className="animate-spin mr-2" /> 加载中…
          </div>
        )}

        {/* KP Grid */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {visibleKPs.map((kp) => {
            const mastery = (kp.mastery_status as MasteryKey) in MASTERY_CONFIG
              ? (kp.mastery_status as MasteryKey) : "new";
            const m = MASTERY_CONFIG[mastery];
            const sc = kp.subject ? (SUBJECT_COLORS[kp.subject] || "bg-slate-50 border-slate-200 text-slate-700") : "";
            const preview = kp.content ? kp.content.replace(/[#*`>]/g, "").replace(/\n+/g, " ").trim().slice(0, 80) : null;
            return (
              <Link key={kp.id} href={`/knowledge/${kp.id}`}>
                <Card className="h-full hover:shadow-md hover:border-primary/30 transition-all cursor-pointer">
                  <CardContent className="py-3.5 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {kp.subject && (
                          <span className={`text-[11px] px-2 py-0.5 rounded-full border font-medium ${sc}`}>
                            {kp.subject}
                          </span>
                        )}
                      </div>
                      <span className={`shrink-0 text-[11px] px-2 py-0.5 rounded-full font-medium ${m.color}`}>
                        {m.label}
                      </span>
                    </div>
                    <p className="font-semibold text-sm text-foreground leading-snug">{kp.name}</p>
                    {preview && (
                      <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">{preview}…</p>
                    )}
                    <div className="flex items-center gap-3 pt-0.5 text-[11px] text-muted-foreground">
                      {kp.next_review_date ? (
                        <span className="flex items-center gap-1">
                          <Clock size={10} />
                          {new Date(kp.next_review_date) <= new Date() ? "今天复习" : `复习 ${new Date(kp.next_review_date).toLocaleDateString("zh-CN")}`}
                        </span>
                      ) : mastery !== "new" && kp.stability ? (
                        <span>稳定性 {kp.stability.toFixed(1)}</span>
                      ) : (
                        <span className="flex items-center gap-1"><BookOpen size={10} /> 尚未复习</span>
                      )}
                      {(kp.flashcard_count ?? 0) > 0 && (
                        <span className="flex items-center gap-1"><Layers size={10} />{kp.flashcard_count} 张闪卡</span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>

        {!isLoading && !lessonKPsLoading && visibleKPs.length === 0 && view === "all" && (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center py-14 text-center">
              <BookOpen size={34} className="text-primary/55" />
              <p className="mt-3 font-semibold text-foreground">
                {kps.length === 0 ? "还没有知识点" : "没有匹配的结果"}
              </p>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                {kps.length === 0
                  ? "先生成一篇笔记，知曜会自动抽取知识点并跟踪掌握度。"
                  : "调整搜索或筛选条件，看看其它学科和掌握阶段。"}
              </p>
              {kps.length === 0 && (
                <Link
                  href="/notes"
                  className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-[0_8px_22px_oklch(0.70_0.16_170_/_22%)] transition-all hover:bg-primary/90"
                >
                  <Sparkles size={15} /> 去生成笔记
                </Link>
              )}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
