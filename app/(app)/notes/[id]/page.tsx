"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft, BookOpen, Brain, Layers, Loader2,
  Sparkles, Trash2, AlertCircle, Clock, FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getNote, deleteNote } from "@/lib/api";

const SUBJECT_COLORS: Record<string, string> = {
  数学: "bg-blue-50 text-blue-700 ring-blue-200",
  物理: "bg-purple-50 text-purple-700 ring-purple-200",
  化学: "bg-green-50 text-green-700 ring-green-200",
  生物: "bg-teal-50 text-teal-700 ring-teal-200",
  语文: "bg-red-50 text-red-700 ring-red-200",
  英语: "bg-amber-50 text-amber-700 ring-amber-200",
};

const MASTERY_CONFIG = {
  mastered: { label: "已掌握", color: "bg-green-100 text-green-700" },
  reviewing: { label: "复习中", color: "bg-primary/10 text-primary" },
  learning: { label: "学习中", color: "bg-amber-100 text-amber-700" },
  new: { label: "未开始", color: "bg-slate-100 text-slate-600" },
} as const;

interface KPBrief {
  id: string;
  name: string;
  subject?: string;
  mastery_status: string;
  bloom_level?: string;
  flashcard_count?: number;
}

interface NoteDetail {
  id: string;
  title: string | null;
  subject: string | null;
  source_type: string;
  status: "processing" | "done" | "failed";
  full_version: string | null;
  exam_version: string | null;
  graph_mermaid: string | null;
  difficulty_points: { name: string; reason: string }[];
  flashcards_generated: boolean;
  knowledge_points: KPBrief[];
  created_at: string;
}

type Tab = "full" | "exam" | "graph";

function MermaidView({ code }: { code: string }) {
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!code) return;
    import("mermaid").then((m) => {
      m.default.initialize({ startOnLoad: false, theme: "neutral" });
      m.default.render("mermaid-diagram", code)
        .then((r) => setSvg(r.svg))
        .catch(() => setError(true));
    });
  }, [code]);

  if (error) return (
    <div className="rounded-xl border border-border bg-muted/30 p-4">
      <p className="text-xs text-muted-foreground mb-2">知识框架（原始格式）：</p>
      <pre className="text-xs text-foreground whitespace-pre-wrap font-mono">{code}</pre>
    </div>
  );
  if (!svg) return (
    <div className="flex items-center justify-center py-12 text-muted-foreground">
      <Loader2 size={18} className="animate-spin mr-2" /> 渲染中…
    </div>
  );
  return <div className="overflow-auto rounded-xl border border-border bg-white p-4" dangerouslySetInnerHTML={{ __html: svg }} />;
}

function MarkdownBody({ content }: { content: string }) {
  return (
    <div
      className="prose prose-sm max-w-none text-foreground
        prose-headings:text-foreground prose-headings:font-semibold
        prose-p:text-muted-foreground prose-p:leading-relaxed
        prose-strong:text-foreground prose-strong:font-semibold
        prose-code:text-primary prose-code:bg-primary/8 prose-code:px-1 prose-code:rounded
        prose-pre:bg-muted prose-pre:text-foreground
        prose-li:text-muted-foreground prose-li:leading-relaxed
        prose-blockquote:border-primary/30 prose-blockquote:text-muted-foreground"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

export default function NoteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("full");

  const { data: note, isLoading, isError } = useQuery<NoteDetail>({
    queryKey: ["note", id],
    queryFn: () => getNote(id) as Promise<NoteDetail>,
    enabled: !!id,
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteNote(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      router.replace("/notes");
    },
  });

  if (isLoading) return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Loader2 size={28} className="animate-spin text-primary" />
    </div>
  );

  if (isError || !note) return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-muted-foreground">
      <AlertCircle size={32} />
      <p>加载笔记失败</p>
      <Button variant="outline" onClick={() => router.back()}>返回</Button>
    </div>
  );

  const sc = note.subject ? (SUBJECT_COLORS[note.subject] || "bg-slate-50 text-slate-700 ring-slate-200") : "";

  const TABS: { key: Tab; label: string; icon: typeof BookOpen; content: string | null }[] = [
    { key: "full", label: "精读版", icon: BookOpen, content: note.full_version },
    { key: "exam", label: "应考速览", icon: Sparkles, content: note.exam_version },
    { key: "graph", label: "知识框架", icon: Brain, content: note.graph_mermaid },
  ];

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 pb-16 md:p-8">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft size={14} /> 返回笔记库
      </button>

      {/* Header */}
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            {note.subject && (
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${sc}`}>
                {note.subject}
              </span>
            )}
            {note.status === "processing" && (
              <span className="flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 ring-1 ring-amber-200">
                <Loader2 size={10} className="animate-spin" /> AI 整理中…
              </span>
            )}
            {note.status === "failed" && (
              <span className="rounded-full bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 ring-1 ring-red-200">
                生成失败
              </span>
            )}
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="text-muted-foreground hover:text-destructive hover:bg-destructive/8 shrink-0"
            onClick={() => { if (confirm("确认删除这篇笔记？")) deleteMut.mutate(); }}
            disabled={deleteMut.isPending}
          >
            {deleteMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
          </Button>
        </div>

        <h1 className="text-2xl font-bold text-foreground leading-snug">
          {note.title || "未命名笔记"}
        </h1>

        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><Clock size={11} />{note.created_at?.slice(0, 10)}</span>
          {note.knowledge_points?.length > 0 && (
            <span className="flex items-center gap-1"><FileText size={11} />{note.knowledge_points.length} 个知识点</span>
          )}
          {note.flashcards_generated && (
            <span className="flex items-center gap-1"><Layers size={11} />已生成闪卡</span>
          )}
        </div>
      </div>

      {/* 三件套 Tabs */}
      {note.status === "done" ? (
        <div className="space-y-4">
          <div className="flex gap-1 rounded-xl bg-muted p-1">
            {TABS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={cn(
                  "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition-all",
                  tab === key
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon size={13} />{label}
              </button>
            ))}
          </div>

          <div className="min-h-[200px]">
            {TABS.map(({ key, label, content }) => (
              tab === key && (
                <div key={key}>
                  {content ? (
                    key === "graph" ? (
                      <MermaidView code={content} />
                    ) : (
                      <Card>
                        <CardContent className="py-6 px-5">
                          <MarkdownBody content={content} />
                        </CardContent>
                      </Card>
                    )
                  ) : (
                    <div className="flex flex-col items-center py-12 text-muted-foreground gap-2">
                      <BookOpen size={28} className="opacity-40" />
                      <p className="text-sm">暂无{label}内容</p>
                    </div>
                  )}
                </div>
              )
            ))}
          </div>
        </div>
      ) : note.status === "processing" ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center py-14 text-center gap-3">
            <Loader2 size={32} className="animate-spin text-primary/60" />
            <p className="font-semibold text-foreground">AI 正在整理笔记三件套</p>
            <p className="text-sm text-muted-foreground">精读版、应考速览、知识框架图生成中，通常需要 30–60 秒</p>
          </CardContent>
        </Card>
      ) : (
        <Card className="border-dashed border-destructive/30">
          <CardContent className="flex flex-col items-center py-10 text-center gap-2">
            <AlertCircle size={28} className="text-destructive/60" />
            <p className="text-sm text-muted-foreground">笔记生成失败，请重新提交</p>
          </CardContent>
        </Card>
      )}

      {/* 难点提示 */}
      {note.difficulty_points?.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-semibold text-foreground">重点难点</p>
          <div className="space-y-2">
            {note.difficulty_points.map((d, i) => (
              <div key={i} className="rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3">
                <p className="text-sm font-medium text-amber-800">{d.name}</p>
                {d.reason && <p className="mt-0.5 text-xs text-amber-700/80">{d.reason}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 关联知识点 */}
      {note.knowledge_points?.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-foreground">关联知识点 ({note.knowledge_points.length})</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {note.knowledge_points.map((kp) => {
              const mastery = (kp.mastery_status as keyof typeof MASTERY_CONFIG) in MASTERY_CONFIG
                ? (kp.mastery_status as keyof typeof MASTERY_CONFIG)
                : "new";
              const m = MASTERY_CONFIG[mastery];
              return (
                <Link
                  key={kp.id}
                  href={`/knowledge/${kp.id}`}
                  className="flex items-center justify-between rounded-xl border border-border bg-card px-4 py-3 hover:border-primary/30 hover:bg-primary/4 transition-colors"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{kp.name}</p>
                    {kp.subject && <p className="text-xs text-muted-foreground">{kp.subject}</p>}
                  </div>
                  <span className={`ml-2 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${m.color}`}>
                    {m.label}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
