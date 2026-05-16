import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

const SUBJECTS = [
  { name: "数学", kp: 38, mastered: 22, rate: 58 },
  { name: "物理", kp: 31, mastered: 15, rate: 48 },
  { name: "英语", kp: 29, mastered: 17, rate: 59 },
  { name: "化学", kp: 24, mastered: 0, rate: 0 },
  { name: "语文", kp: 20, mastered: 0, rate: 0 },
];

export function SubjectProgress() {
  return (
    <Card className="border-border/60">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold">学科掌握率</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {SUBJECTS.map((s) => (
          <div key={s.name}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-foreground">{s.name}</span>
              <span className="text-xs text-muted-foreground">{s.rate}%</span>
            </div>
            <Progress value={s.rate} className="h-1.5" />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
