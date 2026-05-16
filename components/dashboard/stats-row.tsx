import { Card, CardContent } from "@/components/ui/card";
import { Brain, Layers, Clock, AlertCircle } from "lucide-react";

const STATS = [
  { label: "知识点总数", value: "142", sub: "较上周 +8", icon: Brain, color: "text-violet-600" },
  { label: "今日待复习", value: "23", sub: "闪卡", icon: Layers, color: "text-amber-600" },
  { label: "本周学习", value: "4.2h", sub: "17个番茄钟", icon: Clock, color: "text-emerald-600" },
  { label: "错题待攻克", value: "11", sub: "题", icon: AlertCircle, color: "text-rose-600" },
];

export function StatsRow() {
  return (
    <div className="grid grid-cols-4 gap-4">
      {STATS.map((s) => (
        <Card key={s.label} className="border-border/60">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-muted-foreground font-medium">{s.label}</p>
                <p className="text-2xl font-bold mt-1 text-foreground">{s.value}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{s.sub}</p>
              </div>
              <div className={`p-2 rounded-lg bg-current/8 ${s.color}`}>
                <s.icon size={18} className={s.color} strokeWidth={1.8} />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
