"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertCircle, CheckCircle2, RotateCcw, ChevronDown, ChevronUp, Target } from "lucide-react";

const MOCK_MISTAKES = [
  {
    id: "1",
    subject: "物理",
    question: "质量为 2 kg 的物体在水平面上做匀速运动，已知动摩擦因数 μ=0.3，g=10m/s²，求物体所受摩擦力大小。",
    your_answer: "f = μmg = 0.3 × 2 × 10 = 6 N",
    reference: "f = μN = μmg = 0.3 × 2 × 10 = 6 N\n\n注意：匀速运动时合力为零，摩擦力等于推力（如有），此题缺少推力信息，若纯匀速则摩擦力即为6N。",
    knowledge_points: ["滑动摩擦力", "牛顿第一定律"],
    error_count: 2,
    last_error: "2026-05-15",
    can_remove: false,
  },
  {
    id: "2",
    subject: "数学",
    question: "已知 f(x) = x³ - 3x，求 f(x) 的单调递增区间。",
    your_answer: "f'(x) = 3x² - 3 = 0，x = ±1。单调递增区间为 (-∞, -1) 和 (1, +∞)。",
    reference: "f'(x) = 3x² - 3\n令 f'(x) > 0，得 x < -1 或 x > 1\n所以单调递增区间为 (-∞, -1) 和 (1, +∞)。\n\n✓ 答案正确，注意区间端点不包含（开区间）。",
    knowledge_points: ["导数", "单调性"],
    error_count: 1,
    last_error: "2026-05-14",
    can_remove: true,
  },
  {
    id: "3",
    subject: "化学",
    question: "下列物质中，属于电解质的是：A. NaCl  B. 蔗糖  C. 酒精  D. 铁",
    your_answer: "D. 铁",
    reference: "A. NaCl（氯化钠）\n\nNaCl 溶于水或熔融状态下能导电，是强电解质。铁是单质，不是化合物，因此不属于电解质或非电解质范畴。",
    knowledge_points: ["电解质", "强弱电解质判断"],
    error_count: 3,
    last_error: "2026-05-16",
    can_remove: false,
  },
  {
    id: "4",
    subject: "英语",
    question: "Fill in the blank: He insisted that she ______ (come) to the party.",
    your_answer: "came",
    reference: "come（原形）\n\n\"insist that\" 后接虚拟语气，从句用动词原形（或 should + 原形），不随主语变化。",
    knowledge_points: ["虚拟语气", "情态动词"],
    error_count: 2,
    last_error: "2026-05-13",
    can_remove: false,
  },
];

const SUBJECT_COLORS: Record<string, string> = {
  数学: "bg-blue-100 text-blue-700",
  物理: "bg-purple-100 text-purple-700",
  化学: "bg-green-100 text-green-700",
  英语: "bg-amber-100 text-amber-700",
};

export default function MistakesPage() {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [removed, setRemoved] = useState<string[]>([]);
  const [practicing, setPracticing] = useState<string | null>(null);

  const visible = MOCK_MISTAKES.filter((m) => !removed.includes(m.id));

  function toggle(id: string) {
    setExpanded((prev) => (prev === id ? null : id));
  }

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">错题本</h1>
          <p className="text-sm text-muted-foreground mt-0.5">共 {visible.length} 道错题待攻克</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <AlertCircle size={14} className="text-destructive" />
          连续答对2次可自动移除
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "待攻克", value: visible.length, color: "text-destructive" },
          { label: "本周新增", value: 3, color: "text-amber-600" },
          { label: "已攻克", value: removed.length + 5, color: "text-green-600" },
        ].map(({ label, value, color }) => (
          <Card key={label} size="sm">
            <CardContent className="py-3.5 text-center">
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Mistake list */}
      <div className="space-y-3">
        {visible.map((m) => {
          const isExpanded = expanded === m.id;
          const sc = SUBJECT_COLORS[m.subject] || "bg-muted text-muted-foreground";
          return (
            <Card key={m.id} className={`transition-all ${isExpanded ? "ring-1 ring-primary/30" : ""}`}>
              {/* Header row */}
              <CardContent className="py-4 space-y-3">
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${sc}`}>{m.subject}</span>
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <AlertCircle size={11} className="text-destructive" /> 错了 {m.error_count} 次
                      </span>
                      <span className="text-xs text-muted-foreground">· {m.last_error}</span>
                    </div>
                    <p className="text-sm text-foreground leading-relaxed line-clamp-2">{m.question}</p>
                  </div>
                  <button
                    onClick={() => toggle(m.id)}
                    className="shrink-0 text-muted-foreground hover:text-foreground transition-colors mt-0.5"
                  >
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                </div>

                {/* Knowledge points */}
                <div className="flex gap-1.5 flex-wrap">
                  {m.knowledge_points.map((kp) => (
                    <span key={kp} className="text-[11px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                      {kp}
                    </span>
                  ))}
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="space-y-3 pt-1 border-t border-border">
                    <div>
                      <p className="text-xs font-medium text-destructive mb-1.5">你的答案</p>
                      <p className="text-sm text-foreground bg-destructive/5 rounded-lg px-3 py-2 leading-relaxed">
                        {m.your_answer}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-green-600 mb-1.5">正确解析</p>
                      <p className="text-sm text-foreground bg-green-50 border border-green-100 rounded-lg px-3 py-2 leading-relaxed whitespace-pre-line">
                        {m.reference}
                      </p>
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    className="gap-1.5"
                    onClick={() => setPracticing(m.id)}
                  >
                    <Target size={13} /> 重新练习
                  </Button>
                  {m.can_remove && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1.5 text-green-600 border-green-200 hover:bg-green-50"
                      onClick={() => setRemoved((prev) => [...prev, m.id])}
                    >
                      <CheckCircle2 size={13} /> 已掌握，移除
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {visible.length === 0 && (
        <div className="text-center py-20 space-y-3">
          <CheckCircle2 size={40} className="mx-auto text-green-500" />
          <p className="font-semibold text-foreground">错题本已清空！</p>
          <p className="text-sm text-muted-foreground">保持这个状态，继续加油！</p>
        </div>
      )}
    </div>
  );
}
