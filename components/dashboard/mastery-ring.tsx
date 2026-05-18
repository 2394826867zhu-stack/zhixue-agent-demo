"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

const DATA = [
  { name: "已掌握", value: 54, color: "#22c55e" },
  { name: "复习中", value: 41, color: "#8b5cf6" },
  { name: "学习中", value: 31, color: "#f59e0b" },
  { name: "未开始", value: 16, color: "#94a3b8" },
];
const TOTAL = DATA.reduce((s, d) => s + d.value, 0);

export function MasteryRing() {
  return (
    <Card className="border-border/60">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold">知识点掌握度</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative h-36">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={DATA}
                cx="50%"
                cy="50%"
                innerRadius={44}
                outerRadius={64}
                paddingAngle={2}
                dataKey="value"
                strokeWidth={0}
              >
                {DATA.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => {
                  const count = Number(value ?? 0);
                  return [`${count} 个 (${Math.round(count / TOTAL * 100)}%)`, ""];
                }}
                contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)" }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-2xl font-bold text-foreground">{TOTAL}</span>
            <span className="text-xs text-muted-foreground">知识点</span>
          </div>
        </div>
        <div className="mt-3 space-y-1.5">
          {DATA.map((d) => (
            <div key={d.name} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                <span className="text-muted-foreground">{d.name}</span>
              </div>
              <span className="font-medium text-foreground">{d.value}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
