"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft, BookOpen, Brain, Layers, Loader2,
  Target, AlertCircle, CheckCircle2, Circle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getKP, updateKP } from "@/lib/api";

const MASTERY_STEPS: { key: string; label: string; color: string; bg: string }[] = [
  { key: "new",      label: "未开始", color: "text-slate-500",  bg: "bg-slate-100" },
  { key: "learning", label: "学习中", color: "text-amber-600",  bg: "bg-amber-100" },
  { key: "reviewing",label: "复习中", color: "text-primary",    bg: "bg-primary/10" },
  { key: "mastered", label: "已掌握", color: "text-green-600",  bg: "bg-green-100" },
];

const BLOOM_LABELS: Record<string, string> = {
  remember: "记忆", understand: "理解", apply: "应用",
  analyze: "分析", evaluate: "评价", create: "创造",
};

const SUBJECT_COLORS: Record<string, string> = {
  数学: "bg-blue-50 text-blue-700 ring-blue-200",
  物理: "bg-purple-50 text-purple-700 ring-purple-200",
  化学: "bg-green-50 text-green-700 ring-green-200",
  生物: "bg-teal-50 text-teal-700 ring-teal-200",
  语文: "bg-red-50 text-red-700 ring-red-200",
  英语: "bg-amber-50 text-amber-700 ring-amber-200",
};

interface KPDetail {
  id: string;
  name: string;
  subject?: string;
  content?: string;
  key_formula?: string;
  bloom_level?: string;
  mastery_status: string;
  flashcard_count?: number;
  note_id?: string | null;
  tags?: string[];
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

export default function KPDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: kp, isLoading, isError } = useQuery<KPDetail>({
    queryKey: ["kp", id],
    queryFn: () => getKP(id) as Promise<KPDetail>,
    enabled: !!id,
  });

  const updateMut = useMutation({
    mutationFn: (mastery_status: string) => updateKP(id, { mastery_status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["kp", id] });
      queryClient.invalidateQueries({ queryKey: ["kps"] });
      queryClient.invalidateQueries({ queryKey: ["kp-stats"] });
    },
  });

  if (isLoading) return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Loader2 size={28} className="animate-spin text-primary" />
    </div>
  );

  if (isError || !kp) return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-muted-foreground">
      <AlertCircle size={32} />
      <p>加载知识点失败</p>
      <Button variant="outline" onClick={() => router.back()}>返回</Button>
    </div>
  );

  const sc = kp.subject ? (SUBJECT_COLORS[kp.subject] || "bg-slate-50 text-slate-700 ring-slate-200") : "";
  const currentMasteryIdx = MASTERY_STEPS.findIndex((s) => s.key === kp.mastery_status);
  const bloomLabel = kp.bloom_level ? (BLOOM_LABELS[kp.bloom_level] || kp.bloom_level) : null;

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-4 pb-16 md:p-8">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft size={14} /> 返回知识库
      </button>

      {/* Header */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {kp.subject && (
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${sc}`}>
              {kp.subject}
            </span>
          )}
          {bloomLabel && (
            <span className="rounded-full bg-violet-50 px-2.5 py-1 text-xs font-semibold text-violet-700 ring-1 ring-violet-200">
              {bloomLabel}层级
            </span>
          )}
          {kp.tags?.map((tag) => (
            <span key={tag} className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
              #{tag}
            </span>
          ))}
        </div>
        <h1 className="text-2xl font-bold text-foreground">{kp.name}</h1>
      </div>

      {/* Mastery selector */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">掌握进度</p>
        <div className="flex gap-2">
          {MASTERY_STEPS.map((step, i) => {
            const isActive = kp.mastery_status === step.key;
            const isPast = i <= currentMasteryIdx;
            return (
              <button
                key={step.key}
                onClick={() => updateMut.mutate(step.key)}
                disabled={updateMut.isPending}
                className={cn(
                  "flex flex-1 flex-col items-center gap-1 rounded-xl border py-2.5 text-[11px] font-semibold transition-all",
                  isActive
                    ? `${step.bg} ${step.color} border-current/30 shadow-sm`
                    : isPast
                    ? "border-border bg-muted/50 text-muted-foreground"
                    : "border-border bg-card text-muted-foreground hover:border-primary/30"
                )}
              >
                {isActive
                  ? <CheckCircle2 size={14} />
                  : isPast
                  ? <CheckCircle2 size={14} className="opacity-40" />
                  : <Circle size={14} />}
                {step.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Key formula */}
      {kp.key_formula && (
        <Card className="border-primary/20 bg-primary/4">
          <CardContent className="py-4 px-5">
            <p className="mb-2 text-xs font-semibold text-primary uppercase tracking-wide">核心公式 / 关键概念</p>
            <MarkdownBody content={kp.key_formula} />
          </CardContent>
        </Card>
      )}

      {/* Content */}
      {kp.content ? (
        <Card>
          <CardContent className="py-6 px-5">
            <p className="mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">详细解析</p>
            <MarkdownBody content={kp.content} />
          </CardContent>
        </Card>
      ) : (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center py-10 text-center gap-2">
            <Brain size={28} className="text-primary/40" />
            <p className="text-sm text-muted-foreground">暂无详细内容，可通过 AI 管家补充</p>
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        <Link href={`/training?kp=${kp.id}`}>
          <Button variant="outline" className="gap-2">
            <Target size={14} /> 开始专项训练
          </Button>
        </Link>
        <Link href="/flashcards">
          <Button variant="outline" className="gap-2">
            <Layers size={14} />
            {kp.flashcard_count ? `复习 ${kp.flashcard_count} 张闪卡` : "去闪卡复习"}
          </Button>
        </Link>
        {kp.note_id && (
          <Link href={`/notes/${kp.note_id}`}>
            <Button variant="outline" className="gap-2">
              <BookOpen size={14} /> 查看来源笔记
            </Button>
          </Link>
        )}
      </div>
    </div>
  );
}
