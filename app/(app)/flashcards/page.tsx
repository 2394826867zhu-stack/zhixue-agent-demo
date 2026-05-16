"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { RotateCcw, CheckCircle2, ChevronRight } from "lucide-react";

const MOCK_CARDS = [
  {
    id: "1", subject: "数学", front: "等差数列求和公式",
    back: "Sₙ = n(a₁ + aₙ)/2 = na₁ + n(n-1)d/2\n其中 a₁ 为首项，d 为公差，n 为项数。",
    due_in: "今天", stability: 2.4,
  },
  {
    id: "2", subject: "物理", front: "牛顿第二定律",
    back: "F = ma\n合外力等于质量与加速度的乘积。方向与加速度方向相同。",
    due_in: "今天", stability: 5.1,
  },
  {
    id: "3", subject: "化学", front: "阿伏伽德罗定律",
    back: "在相同温度和压力下，相同体积的任何气体含有相同数目的分子（或原子）。\n标准状况下1 mol气体体积约为22.4 L。",
    due_in: "今天", stability: 1.8,
  },
  {
    id: "4", subject: "英语", front: "elaborate (v.)",
    back: "详细说明；精心制作\n- Please elaborate on your point.\n- 请对你的观点进行详细说明。",
    due_in: "今天", stability: 3.2,
  },
  {
    id: "5", subject: "数学", front: "极限的ε-δ定义",
    back: "lim(x→a) f(x) = L 当且仅当：\n对任意 ε > 0，存在 δ > 0，使得当 0 < |x-a| < δ 时，|f(x)-L| < ε。",
    due_in: "今天", stability: 0.9,
  },
];

const RATING_CONFIG = [
  { rating: 1, label: "忘了", desc: "完全不记得", color: "bg-red-500/10 text-red-600 hover:bg-red-500/20 border-red-200" },
  { rating: 2, label: "困难", desc: "很费力想起", color: "bg-orange-500/10 text-orange-600 hover:bg-orange-500/20 border-orange-200" },
  { rating: 3, label: "还好", desc: "犹豫后想起", color: "bg-amber-500/10 text-amber-600 hover:bg-amber-500/20 border-amber-200" },
  { rating: 4, label: "轻松", desc: "立刻记起", color: "bg-green-500/10 text-green-600 hover:bg-green-500/20 border-green-200" },
];

const SUBJECT_COLORS: Record<string, string> = {
  数学: "bg-blue-100 text-blue-700",
  物理: "bg-purple-100 text-purple-700",
  化学: "bg-green-100 text-green-700",
  英语: "bg-amber-100 text-amber-700",
};

export default function FlashcardsPage() {
  const [current, setCurrent] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [done, setDone] = useState<string[]>([]);
  const [finished, setFinished] = useState(false);

  const card = MOCK_CARDS[current];
  const total = MOCK_CARDS.length;
  const progress = (done.length / total) * 100;

  function handleFlip() {
    setFlipped((f) => !f);
  }

  function handleRate(rating: number) {
    const newDone = [...done, card.id];
    setDone(newDone);
    if (current + 1 >= total) {
      setFinished(true);
    } else {
      setCurrent((c) => c + 1);
      setFlipped(false);
    }
  }

  function handleRestart() {
    setCurrent(0);
    setFlipped(false);
    setDone([]);
    setFinished(false);
  }

  if (finished) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-6">
          <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
            <CheckCircle2 className="text-primary" size={40} />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground">今日复习完成！</h2>
            <p className="text-muted-foreground mt-1">共复习了 {total} 张卡片，保持这个节奏！</p>
          </div>
          <div className="grid grid-cols-2 gap-4 w-full max-w-sm">
            <Card size="sm">
              <CardContent className="py-4 text-center">
                <div className="text-2xl font-bold text-primary">{total}</div>
                <div className="text-xs text-muted-foreground mt-0.5">已复习</div>
              </CardContent>
            </Card>
            <Card size="sm">
              <CardContent className="py-4 text-center">
                <div className="text-2xl font-bold text-green-600">3</div>
                <div className="text-xs text-muted-foreground mt-0.5">明日到期</div>
              </CardContent>
            </Card>
          </div>
          <Button onClick={handleRestart} variant="outline" size="lg" className="gap-2">
            <RotateCcw size={16} /> 再练一遍
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">闪卡复习</h1>
          <p className="text-sm text-muted-foreground mt-0.5">今日到期 {total} 张</p>
        </div>
        <div className="text-right">
          <p className="text-sm font-medium text-foreground">{done.length} / {total}</p>
          <p className="text-xs text-muted-foreground">已完成</p>
        </div>
      </div>

      {/* Progress */}
      <Progress value={progress} className="h-1.5" />

      {/* Card */}
      <div className="relative" style={{ perspective: "1000px" }}>
        <div
          className="relative w-full transition-transform duration-500 cursor-pointer"
          style={{ transformStyle: "preserve-3d", transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)", minHeight: "300px" }}
          onClick={handleFlip}
        >
          {/* Front */}
          <div
            className="absolute inset-0 w-full rounded-2xl border border-border bg-card shadow-md flex flex-col items-center justify-center p-10 text-center"
            style={{ backfaceVisibility: "hidden" }}
          >
            <span className={`text-xs px-2.5 py-1 rounded-full font-medium mb-6 ${SUBJECT_COLORS[card.subject] || "bg-muted text-muted-foreground"}`}>
              {card.subject}
            </span>
            <h2 className="text-2xl font-semibold text-foreground leading-snug">{card.front}</h2>
            <p className="text-sm text-muted-foreground mt-6 flex items-center gap-1.5">
              点击翻转查看答案 <ChevronRight size={14} />
            </p>
          </div>

          {/* Back */}
          <div
            className="absolute inset-0 w-full rounded-2xl border border-primary/30 bg-primary/5 shadow-md flex flex-col items-center justify-center p-10 text-center"
            style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}
          >
            <span className={`text-xs px-2.5 py-1 rounded-full font-medium mb-6 ${SUBJECT_COLORS[card.subject] || "bg-muted text-muted-foreground"}`}>
              {card.subject}
            </span>
            <p className="text-base text-foreground leading-relaxed whitespace-pre-line">{card.back}</p>
          </div>
        </div>
      </div>

      {/* Rating buttons — only show when flipped */}
      <div className={`grid grid-cols-4 gap-3 transition-opacity duration-300 ${flipped ? "opacity-100" : "opacity-0 pointer-events-none"}`}>
        {RATING_CONFIG.map(({ rating, label, desc, color }) => (
          <button
            key={rating}
            onClick={() => handleRate(rating)}
            className={`flex flex-col items-center py-3 px-2 rounded-xl border text-center transition-all ${color}`}
          >
            <span className="font-semibold text-sm">{label}</span>
            <span className="text-[11px] mt-0.5 opacity-70">{desc}</span>
          </button>
        ))}
      </div>

      {/* Hint */}
      {!flipped && (
        <p className="text-center text-xs text-muted-foreground">
          回想答案后再翻转，评分更准确
        </p>
      )}
    </div>
  );
}
