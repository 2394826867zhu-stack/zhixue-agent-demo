"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileText,
  Layers3,
  Lightbulb,
  Loader2,
  Search,
  Sparkles,
  Wand2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";
import { generateNoteWithAgent, listNotes } from "@/lib/api";
import { cn } from "@/lib/utils";

const SUBJECTS = ["数学", "物理", "化学", "生物", "语文", "英语", "历史", "地理", "政治"];

interface Note {
  id: string;
  title: string;
  subject: string;
  summary?: string;
  kp_count?: number;
  created_at: string;
}

const SUBJECT_COLORS: Record<string, string> = {
  数学: "bg-sky-500/10 text-sky-700 ring-sky-500/15",
  物理: "bg-violet-500/10 text-violet-700 ring-violet-500/15",
  化学: "bg-emerald-500/10 text-emerald-700 ring-emerald-500/15",
  生物: "bg-teal-500/10 text-teal-700 ring-teal-500/15",
  语文: "bg-rose-500/10 text-rose-700 ring-rose-500/15",
  英语: "bg-amber-500/10 text-amber-700 ring-amber-500/15",
  历史: "bg-orange-500/10 text-orange-700 ring-orange-500/15",
  地理: "bg-cyan-500/10 text-cyan-700 ring-cyan-500/15",
  政治: "bg-pink-500/10 text-pink-700 ring-pink-500/15",
};

const MOCK_NOTES: Note[] = [
  {
    id: "1",
    title: "等差数列与等比数列",
    subject: "数学",
    summary: "等差数列公差恒定，等比数列公比恒定。求和公式推导及应用场景对比分析。",
    kp_count: 8,
    created_at: "2026-05-16",
  },
  {
    id: "2",
    title: "牛顿三大运动定律",
    subject: "物理",
    summary: "惯性定律、加速度定律、作用反作用定律的条件与适用范围，力学分析方法总结。",
    kp_count: 12,
    created_at: "2026-05-15",
  },
  {
    id: "3",
    title: "氧化还原反应基础",
    subject: "化学",
    summary: "化合价变化判断氧化还原，氧化剂还原剂的判断，电子转移守恒配平法。",
    kp_count: 6,
    created_at: "2026-05-14",
  },
  {
    id: "4",
    title: "细胞的能量供应与利用",
    subject: "生物",
    summary: "ATP的合成与水解，细胞呼吸与光合作用的关系，能量代谢调节机制。",
    kp_count: 10,
    created_at: "2026-05-13",
  },
];

function GeneratePanel({ onSuccess }: { onSuccess: () => void }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [topic, setTopic] = useState("");
  const [subject, setSubject] = useState(SUBJECTS[0]);

  const generateMutation = useMutation({
    mutationFn: () => {
      const raw = topic.trim();
      const isLongContent = raw.length > 120 || raw.includes("\n");
      return generateNoteWithAgent({
        topic: isLongContent ? raw.slice(0, 60) : raw,
        subject,
        content: isLongContent ? raw : undefined,
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      setTopic("");
      if (data.note_id) {
        router.push(`/notes/${data.note_id}`);
        return;
      }
      onSuccess();
    },
  });

  const errorMessage =
    generateMutation.error instanceof Error
      ? generateMutation.error.message
      : "生成失败，请检查网络后重试。";

  return (
    <Card className="border-primary/15 bg-gradient-to-br from-card via-card to-primary/5">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Wand2 size={17} className="text-primary" />
              AI 生成学习笔记
            </CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              粘贴章节、题目或课堂内容，知曜会提炼知识点并同步生成复习入口。
            </p>
          </div>
          <Badge variant="secondary">低压力整理</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div>
          <label className="mb-2 block text-sm font-semibold text-foreground">学科</label>
          <div className="flex flex-wrap gap-2">
            {SUBJECTS.map((s) => (
              <button
                key={s}
                onClick={() => setSubject(s)}
                className={cn(
                  "rounded-full border px-3.5 py-1.5 text-sm font-semibold transition-all",
                  subject === s
                    ? "border-primary bg-primary text-primary-foreground shadow-[0_8px_20px_oklch(0.70_0.16_170_/_18%)]"
                    : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground"
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-2 block text-sm font-semibold text-foreground">主题或原文</label>
          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="例如：粘贴一段教材内容，或输入“牛顿第二定律的应用题整理”"
            className="min-h-[148px] w-full resize-none rounded-2xl border border-border bg-background/80 px-4 py-3 text-sm leading-relaxed text-foreground outline-none transition-all placeholder:text-muted-foreground focus:border-primary/45 focus:ring-4 focus:ring-primary/15"
          />
        </div>

        <div className="grid gap-3 rounded-2xl border border-dashed border-primary/20 bg-primary/5 p-4 md:grid-cols-3">
          {[
            { title: "提炼知识点", text: "自动拆成可复习的概念" },
            { title: "生成闪卡", text: "同步到后续记忆任务" },
            { title: "安排复习", text: "给出下一步学习建议" },
          ].map((item) => (
            <div key={item.title} className="space-y-1">
              <p className="text-xs font-semibold text-primary">{item.title}</p>
              <p className="text-xs leading-relaxed text-muted-foreground">{item.text}</p>
            </div>
          ))}
        </div>

        <Button
          onClick={() => generateMutation.mutate()}
          disabled={!topic.trim() || generateMutation.isPending}
          size="lg"
          className="w-full gap-2"
        >
          {generateMutation.isPending ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              正在整理上下文...
            </>
          ) : (
            <>
              <Sparkles size={16} />
              让 Agent 生成笔记
            </>
          )}
        </Button>

        {generateMutation.isSuccess && (
          <div className="flex items-center gap-2.5 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-3.5 text-sm font-medium text-emerald-700">
            <CheckCircle2 size={16} />
            Agent 已开始生成笔记，正在跳转到详情页。
          </div>
        )}

        {generateMutation.isError && (
          <div className="rounded-2xl border border-destructive/20 bg-destructive/5 p-3.5 text-sm text-destructive">
            {errorMessage}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function NoteCard({ note }: { note: Note }) {
  return (
    <Link href={`/notes/${note.id}`} className="block group/card">
    <Card size="sm" className="cursor-pointer hover:border-primary/35 hover:shadow-[var(--shadow-card-hover)]">
      <CardContent className="space-y-4 py-1">
        <div className="flex items-start justify-between gap-3">
          <span
            className={cn(
              "rounded-full px-2.5 py-1 text-xs font-semibold ring-1",
              SUBJECT_COLORS[note.subject] || "bg-muted text-muted-foreground ring-border"
            )}
          >
            {note.subject}
          </span>
          <ChevronRight size={16} className="mt-0.5 shrink-0 text-muted-foreground transition-colors group-hover/card:text-primary" />
        </div>
        <div>
          <h3 className="text-base font-semibold leading-snug text-foreground">{note.title}</h3>
          {note.summary && (
            <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-muted-foreground">{note.summary}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t border-border/70 pt-3 text-xs font-medium text-muted-foreground">
          {note.kp_count != null && (
            <span className="flex items-center gap-1.5">
              <FileText size={12} />
              {note.kp_count} 个知识点
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <Clock size={12} />
            {note.created_at?.slice(0, 10)}
          </span>
        </div>
      </CardContent>
    </Card>
    </Link>
  );
}

export default function NotesPage() {
  const [mode, setMode] = useState<"list" | "generate">("list");
  const [filterSubject, setFilterSubject] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const { data: apiNotes, isError, isLoading } = useQuery<Note[]>({
    queryKey: ["notes"],
    queryFn: () => listNotes(1),
  });

  const allNotes: Note[] = useMemo(
    () => (isError || (!isLoading && !apiNotes) ? MOCK_NOTES : apiNotes ?? []),
    [apiNotes, isError, isLoading]
  );

  const subjects = useMemo(() => [...new Set(allNotes.map((n) => n.subject))], [allNotes]);
  const filtered = useMemo(() => {
    return allNotes.filter((note) => {
      const subjectMatch = filterSubject ? note.subject === filterSubject : true;
      const keyword = query.trim().toLowerCase();
      const queryMatch = keyword
        ? `${note.title} ${note.summary ?? ""} ${note.subject}`.toLowerCase().includes(keyword)
        : true;
      return subjectMatch && queryMatch;
    });
  }, [allNotes, filterSubject, query]);

  const totalKnowledgePoints = allNotes.reduce((sum, note) => sum + (note.kp_count ?? 0), 0);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-8">
      <section className="overflow-hidden rounded-[1.75rem] border border-border/75 bg-card shadow-[var(--shadow-card)]">
        <div className="grid gap-6 p-5 md:grid-cols-[1.35fr_0.65fr] md:p-7">
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="bg-primary/10 text-primary">
                AI 学习内容库
              </Badge>
              <Badge variant="outline">自动沉淀知识点</Badge>
            </div>
            <div className="max-w-2xl">
              <h1 className="text-2xl font-bold tracking-normal text-foreground md:text-3xl">
                把零散内容整理成可复习的学习资产
              </h1>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground md:text-base">
                知曜会把课堂记录、错题和想法整理成笔记、知识点与闪卡，让你不用从空白开始。
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button onClick={() => setMode("generate")} size="lg" className="gap-2">
                <Sparkles size={17} />
                生成新笔记
              </Button>
              <Button variant="outline" size="lg" className="gap-2" onClick={() => setMode("list")}>
                <BookOpen size={17} />
                查看笔记库
              </Button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 md:grid-cols-1">
            {[
              { label: "笔记", value: allNotes.length || "—", hint: "已整理内容" },
              { label: "知识点", value: totalKnowledgePoints || "—", hint: "可复习概念" },
              { label: "AI 建议", value: "3", hint: "今日可执行" },
            ].map((item) => (
              <div key={item.label} className="rounded-2xl border border-border/70 bg-background/75 p-4">
                <p className="text-xs font-medium text-muted-foreground">{item.label}</p>
                <p className="mt-1 text-2xl font-bold text-foreground">{item.value}</p>
                <p className="mt-1 text-xs text-muted-foreground">{item.hint}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <main className="space-y-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="inline-flex w-fit rounded-2xl bg-muted p-1">
              {[
                { key: "list", label: "我的笔记", icon: BookOpen },
                { key: "generate", label: "AI 生成", icon: Sparkles },
              ].map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => setMode(key as "list" | "generate")}
                  className={cn(
                    "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all",
                    mode === key
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon size={15} />
                  {label}
                </button>
              ))}
            </div>

            {mode === "list" && (
              <div className="relative w-full md:w-72">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="搜索笔记或知识点"
                  className="h-10 w-full rounded-xl border border-border bg-card pl-9 pr-3 text-sm outline-none transition-all placeholder:text-muted-foreground focus:border-primary/45 focus:ring-4 focus:ring-primary/15"
                />
              </div>
            )}
          </div>

          {mode === "generate" ? (
            <GeneratePanel onSuccess={() => setMode("list")} />
          ) : (
            <div className="space-y-5">
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setFilterSubject(null)}
                  className={cn(
                    "rounded-full border px-3.5 py-1.5 text-sm font-semibold transition-all",
                    !filterSubject
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground"
                  )}
                >
                  全部
                </button>
                {subjects.map((s) => (
                  <button
                    key={s}
                    onClick={() => setFilterSubject(filterSubject === s ? null : s)}
                    className={cn(
                      "rounded-full border px-3.5 py-1.5 text-sm font-semibold transition-all",
                      filterSubject === s
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground"
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>

              {isLoading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="animate-spin text-primary" size={28} />
                </div>
              ) : filtered.length > 0 ? (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {filtered.map((note) => (
                    <NoteCard key={note.id} note={note} />
                  ))}
                </div>
              ) : (
                <Card className="border-dashed">
                  <CardContent className="flex flex-col items-center py-14 text-center">
                    <BookOpen size={34} className="text-primary/55" />
                    <p className="mt-3 font-semibold text-foreground">
                      {allNotes.length === 0 ? "还没有笔记" : "没有匹配的笔记"}
                    </p>
                    <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                      {allNotes.length === 0
                        ? "上传资料、粘贴课堂内容，或直接让 AI 生成一份复习笔记。"
                        : "换一个关键词，或者让 AI 先帮你整理一份新的学习笔记。"}
                    </p>
                    <Button onClick={() => setMode("generate")} className="mt-5 gap-2">
                      <Sparkles size={15} /> 生成新笔记
                    </Button>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </main>

        <aside className="space-y-4">
          <Card className="bg-gradient-to-br from-primary/10 via-card to-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Lightbulb size={16} className="text-primary" />
                今日整理建议
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                "把昨天的错题归纳成一篇短笔记",
                "为物理章节补 5 张复习闪卡",
                "复盘 1 个还没讲清楚的概念",
              ].map((item, index) => (
                <div key={item} className="flex gap-3 rounded-2xl bg-card/70 p-3">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                    {index + 1}
                  </div>
                  <p className="text-sm leading-relaxed text-foreground">{item}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Layers3 size={16} className="text-primary" />
                知识资产流转
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                { title: "笔记", text: "记录和整理输入内容" },
                { title: "知识点", text: "沉淀成可追踪概念" },
                { title: "闪卡", text: "进入长期记忆复习" },
              ].map((item) => (
                <div key={item.title} className="rounded-2xl border border-border/70 p-3">
                  <p className="text-sm font-semibold text-foreground">{item.title}</p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{item.text}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
