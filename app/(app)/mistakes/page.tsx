"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  AlertCircle, CheckCircle2, RotateCcw, ChevronDown, ChevronUp,
  Target, Loader2, Sparkles, XCircle
} from "lucide-react";
import { cn } from "@/lib/utils";
import { listMistakes, retryMistake, submitRetryAnswer, removeMistake } from "@/lib/api";

const BLOOM_LABELS: Record<string, string> = {
  remember: "记忆", understand: "理解", apply: "应用",
  analyze: "分析", evaluate: "评估", create: "创造",
};

interface Mistake {
  id: string;
  question_text: string;
  reference_answer: string;
  user_answer: string | null;
  ai_score: number | null;
  ai_feedback: string | null;
  bloom_level: string;
  question_type: string;
  created_at: string;
}

interface RetryState {
  mistakeId: string;
  retryQuestionId: string;
  questionText: string;
  answer: string;
  submitted: boolean;
  score?: number;
  feedback?: string;
  reference?: string;
  resolved?: boolean;
  loading: boolean;
}

export default function MistakesPage() {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [retry, setRetry] = useState<RetryState | null>(null);

  const { data: mistakes = [], isLoading } = useQuery<Mistake[]>({
    queryKey: ["mistakes"],
    queryFn: () => listMistakes() as Promise<Mistake[]>,
  });

  const removeMut = useMutation({
    mutationFn: (id: string) => removeMistake(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["mistakes"] }),
  });

  async function handleRetry(mistakeId: string) {
    setRetry({ mistakeId, retryQuestionId: "", questionText: "", answer: "", submitted: false, loading: true });
    try {
      const res = await retryMistake(mistakeId);
      setRetry({
        mistakeId,
        retryQuestionId: String(res.retry_question_id),
        questionText: res.question_text,
        answer: "",
        submitted: false,
        loading: false,
      });
    } catch {
      setRetry(null);
    }
  }

  async function handleSubmitRetry() {
    if (!retry || !retry.answer.trim()) return;
    setRetry((r) => r ? { ...r, loading: true } : null);
    try {
      const res = await submitRetryAnswer(retry.mistakeId, retry.retryQuestionId, retry.answer);
      setRetry((r) => r ? {
        ...r,
        loading: false,
        submitted: true,
        score: res.ai_score,
        feedback: res.ai_feedback,
        reference: res.reference_answer,
        resolved: res.mistake_resolved,
      } : null);
      if (res.mistake_resolved) {
        queryClient.invalidateQueries({ queryKey: ["mistakes"] });
      }
    } catch {
      setRetry((r) => r ? { ...r, loading: false } : null);
    }
  }

  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto space-y-5 md:space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">错题本</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading ? "加载中…" : `共 ${mistakes.length} 道错题待攻克`}
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <AlertCircle size={13} className="text-destructive" />
          答对重练题自动移除
        </div>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16 text-muted-foreground">
          <Loader2 size={20} className="animate-spin mr-2" /> 加载中…
        </div>
      )}

      {/* Retry overlay */}
      {retry && (
        <Card className="border-2 border-primary/30 bg-primary/5">
          <CardContent className="py-5 space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-primary flex items-center gap-1.5">
                <Sparkles size={14} /> AI 重练题
              </p>
              <button onClick={() => setRetry(null)} className="text-muted-foreground hover:text-foreground text-xs">取消</button>
            </div>

            {retry.loading && !retry.questionText && (
              <div className="flex items-center gap-2 text-muted-foreground py-2">
                <Loader2 size={15} className="animate-spin" /> AI 正在出题…
              </div>
            )}

            {retry.questionText && !retry.submitted && (
              <>
                <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">{retry.questionText}</p>
                <textarea
                  value={retry.answer}
                  onChange={(e) => setRetry((r) => r ? { ...r, answer: e.target.value } : null)}
                  placeholder="写下你的答案…"
                  className="w-full min-h-[120px] rounded-lg border border-border bg-background px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none"
                />
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setRetry(null)}>取消</Button>
                  <Button
                    size="sm"
                    onClick={handleSubmitRetry}
                    disabled={!retry.answer.trim() || retry.loading}
                    className="gap-1.5"
                  >
                    {retry.loading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                    提交答案
                  </Button>
                </div>
              </>
            )}

            {retry.submitted && (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-14 h-14 rounded-full border-4 flex items-center justify-center shrink-0",
                    retry.resolved ? "border-green-500" : "border-amber-400"
                  )}>
                    <span className={cn("text-lg font-bold", retry.resolved ? "text-green-600" : "text-amber-600")}>
                      {retry.score}
                    </span>
                  </div>
                  <div>
                    {retry.resolved
                      ? <p className="text-sm font-semibold text-green-600 flex items-center gap-1"><CheckCircle2 size={14} /> 已掌握，移出错题本！</p>
                      : <p className="text-sm font-semibold text-amber-600 flex items-center gap-1"><RotateCcw size={14} /> 继续加油，仍需复习</p>}
                    <p className="text-xs text-muted-foreground mt-0.5">{retry.feedback}</p>
                  </div>
                </div>
                {retry.reference && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">参考答案</p>
                    <p className="text-sm text-foreground whitespace-pre-line bg-background/80 rounded-lg p-3 border border-border">
                      {retry.reference}
                    </p>
                  </div>
                )}
                <Button size="sm" variant="outline" onClick={() => setRetry(null)}>关闭</Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {mistakes.map((m) => {
          const isExpanded = expanded === m.id;
          return (
            <Card key={m.id} className={cn("transition-all", isExpanded && "ring-1 ring-primary/30")}>
              <CardContent className="py-4 space-y-3">
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground font-medium">
                        {BLOOM_LABELS[m.bloom_level] ?? m.bloom_level}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                        {m.question_type === "fill_blank" ? "填空" : m.question_type === "calculation" ? "计算" : "简答"}
                      </span>
                      {m.ai_score !== null && (
                        <span className={cn(
                          "text-xs px-2 py-0.5 rounded-full font-medium",
                          (m.ai_score ?? 0) < 60 ? "bg-destructive/10 text-destructive" : "bg-amber-100 text-amber-700"
                        )}>
                          得分 {m.ai_score}
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground">
                        {new Date(m.created_at).toLocaleDateString("zh-CN")}
                      </span>
                    </div>
                    <p className="text-sm text-foreground leading-relaxed line-clamp-2">{m.question_text}</p>
                  </div>
                  <button
                    onClick={() => setExpanded((prev) => prev === m.id ? null : m.id)}
                    className="shrink-0 text-muted-foreground hover:text-foreground transition-colors mt-0.5"
                  >
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                </div>

                {isExpanded && (
                  <div className="space-y-3 pt-1 border-t border-border">
                    {m.user_answer && (
                      <div>
                        <p className="text-xs font-medium text-destructive mb-1.5 flex items-center gap-1">
                          <XCircle size={11} /> 你的答案
                        </p>
                        <p className="text-sm text-foreground bg-destructive/5 rounded-lg px-3 py-2 leading-relaxed">
                          {m.user_answer}
                        </p>
                      </div>
                    )}
                    <div>
                      <p className="text-xs font-medium text-green-600 mb-1.5 flex items-center gap-1">
                        <CheckCircle2 size={11} /> 正确解析
                      </p>
                      <p className="text-sm text-foreground bg-green-50 border border-green-100 rounded-lg px-3 py-2 leading-relaxed whitespace-pre-line">
                        {m.reference_answer}
                      </p>
                    </div>
                    {m.ai_feedback && (
                      <p className="text-xs text-muted-foreground leading-relaxed border-l-2 border-primary/30 pl-3">
                        {m.ai_feedback}
                      </p>
                    )}
                  </div>
                )}

                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    className="gap-1.5"
                    onClick={() => handleRetry(m.id)}
                    disabled={!!retry}
                  >
                    <Target size={13} /> 重新练习
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1.5 text-muted-foreground"
                    onClick={() => removeMut.mutate(m.id)}
                    disabled={removeMut.isPending}
                  >
                    <CheckCircle2 size={13} /> 移出
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {!isLoading && mistakes.length === 0 && (
        <div className="text-center py-20 space-y-3">
          <CheckCircle2 size={40} className="mx-auto text-green-500" />
          <p className="font-semibold text-foreground">错题本已清空！</p>
          <p className="text-sm text-muted-foreground">保持这个状态，继续加油！</p>
        </div>
      )}
    </div>
  );
}
