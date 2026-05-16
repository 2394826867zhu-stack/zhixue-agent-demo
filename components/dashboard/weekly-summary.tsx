import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sparkles } from "lucide-react";

export function WeeklySummary() {
  return (
    <Card className="border-border/60 bg-gradient-to-r from-primary/5 to-primary/0">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-primary" />
          <CardTitle className="text-sm font-semibold">本周学习建议</CardTitle>
          <span className="text-[10px] text-muted-foreground ml-auto">AI生成 · 每周一更新</span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-4 gap-4 mb-4">
          {[
            { label: "新增知识点", value: "8" },
            { label: "闪卡完成率", value: "71%" },
            { label: "训练平均分", value: "74分" },
            { label: "学习时长", value: "4.2h" },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-xl font-bold text-foreground">{s.value}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
        <div className="rounded-lg bg-primary/8 border border-primary/15 px-4 py-3">
          <p className="text-sm text-foreground leading-relaxed">
            本周整体表现良好，物理掌握率偏低（48%），建议下周优先攻克受力分析和动量守恒两个核心知识点。闪卡复习节奏不错，继续保持每日完成率。化学和语文刚开始录入，尽快生成第一批知识点，建立系统框架。
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
