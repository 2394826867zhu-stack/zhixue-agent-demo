"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Target, ChevronRight, Loader2, CheckCircle2,
  Brain, Star, RotateCcw, Sparkles
} from "lucide-react";

const SUBJECTS = ["数学", "物理", "化学", "生物", "英语", "语文"];
const BLOOM_LEVELS = [
  { value: 1, label: "记忆", desc: "识别和回忆事�? },
  { value: 2, label: "理解", desc: "解释概念含义" },
  { value: 3, label: "应用", desc: "用知识解决问�? },
  { value: 4, label: "分析", desc: "拆解与推断关�? },
];

type Phase = "config" | "answering" | "result";

const MOCK_QUESTION = {
  id: "q1",
  bloom_level: 3,
  question: "一列火车沿直线轨道匀加速运动，已知�?秒末的速度�?15 m/s，第5秒末的速度�?25 m/s。求：\n(1) 火车的加速度；\n(2) 火车运动的初速度；\n(3) �?秒内的位移�?,
  reference: "加速度 a = (v�?- v�?/(t�?- t�? = (25-15)/2 = 5 m/s²\n初速度 v₀ = v�?- a×t�?= 15 - 5×3 = 0 m/s\n位移 s = v₀t + ½at² = 0×5 + ½×5×25 = 62.5 m",
  knowledge_points: ["匀变速运�?, "加速度计算", "运动学公�?],
};

const MOCK_RESULT = {
  score: 85,
  feedback: "解题思路清晰，加速度和初速度计算正确！位移计算有小失误：公式代入正确，但建议写出详细的单位换算步骤，在考试中能避免扣分。整体掌握程度良好，建议重点练习�?3)小题类型�?,
  strengths: ["正确识别了匀加速运动模�?, "加速度公式运用准确"],
  improvements: ["计算过程需更规�?, "建议补充单位说明"],
};

export default function TrainingPage() {
  const [phase, setPhase] = useState<Phase>("config");
  const [subject, setSubject] = useState("物理");
  const [bloomLevel, setBloomLevel] = useState(3);
  const [count, setCount] = useState(5);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<typeof MOCK_RESULT | null>(null);

  function handleStart() {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setPhase("answering");
    }, 1200);
  }

  function handleSubmit() {
    if (!answer.trim()) return;
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setResult(MOCK_RESULT);
      setPhase("result");
    }, 1800);
  }

  function handleRestart() {
    setPhase("config");
    setAnswer("");
    setResult(null);
  }

  if (phase === "config") {
    return (
      <div className="p-4 md:p-8 max-w-2xl mx-auto space-y-5 md:space-y-6">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-foreground tracking-tight">训练</h1>
          <p className="text-sm text-muted-foreground mt-0.5">布鲁姆分层出题，精准提升各阶段能�?/p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Target size={16} className="text-primary" /> 配置本次训练
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* Subject */}
            <div>
              <label className="text-sm font-medium text-foreground mb-2 block">学科</label>
              <div className="flex flex-wrap gap-2">
                {SUBJECTS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSubject(s)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                      subject === s
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-background text-muted-foreground border-border hover:border-primary/50"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Bloom level */}
            <div>
              <label className="text-sm font-medium text-foreground mb-2 block">认知层级（布鲁姆分类�?/label>
              <div className="grid grid-cols-2 gap-2">
                {BLOOM_LEVELS.map(({ value, label, desc }) => (
                  <button
                    key={value}
                    onClick={() => setBloomLevel(value)}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      bloomLevel === value
                        ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                        : "border-border bg-background hover:border-primary/40"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <div className={`w-4 h-4 rounded-full text-[10px] flex items-center justify-center font-bold text-white ${
                        bloomLevel === value ? "bg-primary" : "bg-muted-foreground"
                      }`}>
                        {value}
                      </div>
                      <span className="text-sm font-medium text-foreground">{label}</span>
                    </div>
                    <p className="text-xs text-muted-foreground ml-5.5">{desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Count */}
            <div>
              <label className="text-sm font-medium text-foreground mb-2 block">题目数量：{count} �?/label>
              <input
                type="range" min={1} max={10} value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>1 �?/span><span>10 �?/span>
              </div>
            </div>

            <Button onClick={handleStart} disabled={loading} size="lg" className="w-full gap-2">
              {loading ? <><Loader2 size={16} className="animate-spin" /> AI 出题中�?/> : <><Target size={16} /> 开始训�?/>}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (phase === "answering") {
    return (
      <div className="p-4 md:p-8 max-w-2xl mx-auto space-y-5 md:space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-foreground tracking-tight">训练�?/h1>
            <p className="text-sm text-muted-foreground mt-0.5">{subject} · �?1 / {count} �?/p>
          </div>
          <Progress value={0} className="w-32 h-1.5" />
        </div>

        {/* Question */}
        <Card>
          <CardContent className="py-5 space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                L{MOCK_QUESTION.bloom_level} 应用
              </span>
              <div className="flex gap-1">
                {MOCK_QUESTION.knowledge_points.map((kp) => (
                  <span key={kp} className="text-[11px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                    {kp}
                  </span>
                ))}
              </div>
            </div>
            <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">
              {MOCK_QUESTION.question}
            </p>
          </CardContent>
        </Card>

        {/* Answer */}
        <div>
          <label className="text-sm font-medium text-foreground mb-2 block">你的解答</label>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="写下你的解题过程和答案�?
            className="w-full min-h-[180px] rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none"
          />
        </div>

        <div className="flex gap-3">
          <Button variant="outline" onClick={handleRestart} className="gap-2">
            <RotateCcw size={14} /> 退�?          </Button>
          <Button onClick={handleSubmit} disabled={!answer.trim() || loading} className="flex-1 gap-2">
            {loading ? <><Loader2 size={16} className="animate-spin" /> AI 评分中�?/> : <><Sparkles size={16} /> 提交答案</>}
          </Button>
        </div>
      </div>
    );
  }

  // Result phase
  return (
    <div className="p-8 max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-foreground tracking-tight">评分结果</h1>
        <p className="text-sm text-muted-foreground mt-0.5">{subject} · �?1 / {count} �?/p>
      </div>

      {/* Score */}
      <Card>
        <CardContent className="py-6">
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 rounded-full border-4 border-primary flex items-center justify-center shrink-0">
              <span className="text-2xl font-bold text-primary">{result?.score}</span>
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-foreground">AI 综合评分</p>
              <div className="flex items-center gap-1">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Star
                    key={i}
                    size={14}
                    className={i <= Math.round((result?.score || 0) / 20) ? "text-amber-400 fill-amber-400" : "text-muted"}
                  />
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                {result!.score >= 90 ? "优秀" : result!.score >= 75 ? "良好" : result!.score >= 60 ? "合格" : "需要加�?}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Feedback */}
      <Card>
        <CardHeader><CardTitle className="text-sm flex items-center gap-2"><Brain size={14} className="text-primary" /> AI 点评</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-foreground leading-relaxed">{result?.feedback}</p>

          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 rounded-lg bg-green-50 border border-green-100">
              <p className="text-xs font-medium text-green-700 mb-2 flex items-center gap-1"><CheckCircle2 size={12} /> 做得�?/p>
              {result?.strengths.map((s, i) => (
                <p key={i} className="text-xs text-green-600 mt-1">· {s}</p>
              ))}
            </div>
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-100">
              <p className="text-xs font-medium text-amber-700 mb-2 flex items-center gap-1"><Target size={12} /> 可以改进</p>
              {result?.improvements.map((s, i) => (
                <p key={i} className="text-xs text-amber-600 mt-1">· {s}</p>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Reference */}
      <Card>
        <CardHeader><CardTitle className="text-sm">参考答�?/CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-foreground leading-relaxed whitespace-pre-line font-mono bg-muted/50 rounded-lg p-3">
            {MOCK_QUESTION.reference}
          </p>
        </CardContent>
      </Card>

      <div className="flex gap-3">
        <Button variant="outline" onClick={handleRestart} className="gap-2 flex-1">
          <RotateCcw size={14} /> 重新配置
        </Button>
        <Button onClick={() => { setAnswer(""); setPhase("answering"); }} className="flex-1 gap-2">
          下一�?<ChevronRight size={14} />
        </Button>
      </div>
    </div>
  );
}
