"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Target, Loader2, CheckCircle2, XCircle,
  Brain, Star, RotateCcw, Sparkles, ChevronRight, AlertCircle
} from "lucide-react";
import { cn } from "@/lib/utils";
import { startTraining, submitAnswer } from "@/lib/api";

const SUBJECTS = ["数学", "物理", "化学", "生物", "英语", "语文"];

const BLOOM_LABELS: Record<string, string> = {
  remember: "记忆", understand: "理解", apply: "应用",
  analyze: "分析", evaluate: "评估", create: "创造",
};

interface Question {
  id: string;
  bloom_level: string;
  question_type: string;
  question: string;
}

interface AnswerRecord {
  ai_score: number;
  ai_feedback: string;
  reference: string;
  is_wrong: boolean;
}

type Phase = "config" | "answering" | "result";

export default function TrainingPage() {
  const [phase, setPhase] = useState<Phase>("config");
  const [subject, setSubject] = useState("物理");
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [records, setRecords] = useState<Record<string, AnswerRecord>>({});

  async function handleStart() {
    setError(null);
    setLoading(true);
    try {
      const res = await startTraining({ mode: "subject", subject, question_count: count });
      const nextQuestions = res.questions ?? [];
      if (nextQuestions.length === 0) {
        setError("还没有可训练题目。先在笔记页生成笔记或知识点，再回来开始训练。");
        setPhase("config");
        return;
      }
      setSessionId(String(res.id));
      setQuestions(nextQuestions);
      setCurrentIdx(0);
      setCurrentAnswer("");
      setSubmitted(false);
      setRecords({});
      setPhase("answering");
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        "启动失败，请确认已有该学科知识点后重试";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit() {
    if (!currentAnswer.trim() || !sessionId) return;
    const q = questions[currentIdx];
    setLoading(true);
    try {
      const res = await submitAnswer(sessionId, String(q.id), { user_answer: currentAnswer });
      setRecords((prev) => ({
        ...prev,
        [String(q.id)]: {
          ai_score: res.ai_score,
          ai_feedback: res.ai_feedback,
          reference: res.reference,
          is_wrong: res.is_wrong,
        },
      }));
      setSubmitted(true);
    } catch {
      setError("提交失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  function handleNext() {
    if (currentIdx + 1 >= questions.length) {
      setPhase("result");
    } else {
      setCurrentIdx((i) => i + 1);
      setCurrentAnswer("");
      setSubmitted(false);
      setError(null);
    }
  }

  function handleRestart() {
    setPhase("config");
    setSessionId(null);
    setQuestions([]);
    setCurrentIdx(0);
    setCurrentAnswer("");
    setSubmitted(false);
    setRecords({});
    setError(null);
  }

  const answeredCount = Object.keys(records).length;
  const avgScore =
    answeredCount > 0
      ? Math.round(Object.values(records).reduce((s, r) => s + r.ai_score, 0) / answeredCount)
      : 0;

  // ── Config ──────────────────────────────────────────────────────────────
  if (phase === "config") {
    return (
      <div className="p-4 md:p-8 max-w-2xl mx-auto space-y-5 md:space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">训练</h1>
          <p className="text-sm text-muted-foreground mt-0.5">AI 按布鲁姆分层出题，精准提升各阶段能力</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Target size={16} className="text-primary" /> 配置本次训练
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <label className="text-sm font-medium text-foreground mb-2 block">学科</label>
              <div className="flex flex-wrap gap-2">
                {SUBJECTS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSubject(s)}
                    className={cn(
                      "px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors",
                      subject === s
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-background text-muted-foreground border-border hover:border-primary/50"
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-foreground mb-2 block">
                题目数量：{count} 题
              </label>
              <input
                type="range" min={1} max={10} value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>1 题</span><span>10 题</span>
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                <AlertCircle size={15} className="shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <Button onClick={handleStart} disabled={loading} size="lg" className="w-full gap-2">
              {loading
                ? <><Loader2 size={16} className="animate-spin" /> AI 出题中…</>
                : <><Target size={16} /> 开始训练</>}
            </Button>

            <p className="text-xs text-muted-foreground text-center">
              AI 将根据你在 <strong>{subject}</strong> 学科中已有的知识点出题
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Answering ────────────────────────────────────────────────────────────
  if (phase === "answering") {
    const q = questions[currentIdx];
    if (!q) {
      return (
        <div className="p-4 md:p-8 max-w-2xl mx-auto">
          <Card className="border-dashed">
            <CardContent className="flex min-h-[320px] flex-col items-center justify-center py-12 text-center">
              <Target size={36} className="text-primary/55" />
              <h2 className="mt-3 text-xl font-bold text-foreground">暂时没有训练题</h2>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                先生成笔记或补充知识点，知曜就能基于你的学习内容出题。
              </p>
              <Button onClick={handleRestart} className="mt-5 gap-2">
                <RotateCcw size={14} /> 返回配置
              </Button>
            </CardContent>
          </Card>
        </div>
      );
    }
    const record = records[String(q.id)];
    const progress = Math.round((currentIdx / questions.length) * 100);

    return (
      <div className="p-4 md:p-8 max-w-2xl mx-auto space-y-5 md:space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">训练中</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {subject} · 第 {currentIdx + 1} / {questions.length} 题
            </p>
          </div>
          <Progress value={progress} className="w-32 h-1.5" />
        </div>

        <Card>
          <CardContent className="py-5 space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                {BLOOM_LABELS[q.bloom_level] ?? q.bloom_level}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                {q.question_type === "fill_blank" ? "填空" : q.question_type === "calculation" ? "计算" : "简答"}
              </span>
            </div>
            <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">
              {q.question}
            </p>
          </CardContent>
        </Card>

        {!submitted ? (
          <>
            <div>
              <label className="text-sm font-medium text-foreground mb-2 block">你的解答</label>
              <textarea
                value={currentAnswer}
                onChange={(e) => setCurrentAnswer(e.target.value)}
                placeholder="写下你的解题过程和答案…"
                className="w-full min-h-[160px] rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none"
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-destructive text-sm">
                <AlertCircle size={14} /> {error}
              </div>
            )}

            <div className="flex gap-3">
              <Button variant="outline" onClick={handleRestart} className="gap-2">
                <RotateCcw size={14} /> 退出
              </Button>
              <Button
                onClick={handleSubmit}
                disabled={!currentAnswer.trim() || loading}
                className="flex-1 gap-2"
              >
                {loading
                  ? <><Loader2 size={16} className="animate-spin" /> AI 评分中…</>
                  : <><Sparkles size={16} /> 提交答案</>}
              </Button>
            </div>
          </>
        ) : (
          <>
            {/* Result for this question */}
            <Card className={cn(
              "border-2",
              record.is_wrong ? "border-destructive/30 bg-destructive/5" : "border-green-200 bg-green-50/50"
            )}>
              <CardContent className="py-5 space-y-4">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-16 h-16 rounded-full border-4 flex items-center justify-center shrink-0",
                    record.is_wrong ? "border-destructive" : "border-green-500"
                  )}>
                    <span className={cn(
                      "text-xl font-bold",
                      record.is_wrong ? "text-destructive" : "text-green-600"
                    )}>{record.ai_score}</span>
                  </div>
                  <div>
                    <div className="flex items-center gap-1 mb-1">
                      {[1,2,3,4,5].map((i) => (
                        <Star key={i} size={13} className={cn(
                          i <= Math.round(record.ai_score / 20)
                            ? "text-amber-400 fill-amber-400"
                            : "text-muted"
                        )} />
                      ))}
                    </div>
                    <div className="flex items-center gap-1 text-sm">
                      {record.is_wrong
                        ? <><XCircle size={14} className="text-destructive" /><span className="text-destructive font-medium">已加入错题本</span></>
                        : <><CheckCircle2 size={14} className="text-green-600" /><span className="text-green-700 font-medium">掌握良好</span></>}
                    </div>
                  </div>
                </div>

                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1">
                    <Brain size={12} /> AI 点评
                  </p>
                  <p className="text-sm text-foreground leading-relaxed">{record.ai_feedback}</p>
                </div>

                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">参考答案</p>
                  <p className="text-sm text-foreground leading-relaxed whitespace-pre-line font-mono bg-background/80 rounded-lg p-3 border border-border">
                    {record.reference}
                  </p>
                </div>
              </CardContent>
            </Card>

            <div className="flex gap-3">
              <Button variant="outline" onClick={handleRestart} className="gap-2">
                <RotateCcw size={14} /> 退出
              </Button>
              <Button onClick={handleNext} className="flex-1 gap-2">
                {currentIdx + 1 >= questions.length
                  ? <><CheckCircle2 size={14} /> 查看总结</>
                  : <>下一题 <ChevronRight size={14} /></>}
              </Button>
            </div>
          </>
        )}
      </div>
    );
  }

  // ── Result summary ───────────────────────────────────────────────────────
  const wrongCount = Object.values(records).filter((r) => r.is_wrong).length;

  return (
    <div className="p-4 md:p-8 max-w-2xl mx-auto space-y-5 md:space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">训练完成</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {subject} · 共 {questions.length} 题
        </p>
      </div>

      <Card>
        <CardContent className="py-6">
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 rounded-full border-4 border-primary flex items-center justify-center shrink-0">
              <span className="text-2xl font-bold text-primary">{avgScore}</span>
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-foreground">平均得分</p>
              <div className="flex items-center gap-1">
                {[1,2,3,4,5].map((i) => (
                  <Star key={i} size={14} className={cn(
                    i <= Math.round(avgScore / 20) ? "text-amber-400 fill-amber-400" : "text-muted"
                  )} />
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                {wrongCount > 0
                  ? `${wrongCount} 题已加入错题本，建议重点复习`
                  : "全部掌握，表现优秀！"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {questions.map((q, idx) => {
          const r = records[String(q.id)];
          if (!r) return null;
          return (
            <Card key={String(q.id)} className={cn(
              "border",
              r.is_wrong ? "border-destructive/30" : "border-green-200"
            )}>
              <CardContent className="py-4 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-muted-foreground font-medium">#{idx + 1}</span>
                    {r.is_wrong
                      ? <XCircle size={15} className="text-destructive" />
                      : <CheckCircle2 size={15} className="text-green-600" />}
                    <span className={cn(
                      "text-sm font-semibold",
                      r.is_wrong ? "text-destructive" : "text-green-600"
                    )}>{r.ai_score}分</span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {BLOOM_LABELS[q.bloom_level] ?? q.bloom_level}
                  </span>
                </div>
                <p className="text-sm text-foreground line-clamp-2">{q.question}</p>
                <p className="text-xs text-muted-foreground leading-relaxed">{r.ai_feedback}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="flex gap-3">
        <Button variant="outline" onClick={handleRestart} className="flex-1 gap-2">
          <RotateCcw size={14} /> 重新配置
        </Button>
        <Button onClick={() => { setPhase("answering"); setCurrentIdx(0); setSubmitted(false); setCurrentAnswer(""); setRecords({}); }} className="flex-1 gap-2">
          <Target size={14} /> 重做本组
        </Button>
      </div>
    </div>
  );
}
