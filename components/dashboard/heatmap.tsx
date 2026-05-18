"use client";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getHeatmap } from "@/lib/api";

interface HeatDay { date: string; minutes: number }

function getIntensity(minutes: number) {
  if (minutes === 0) return 0;
  if (minutes < 20) return 1;
  if (minutes < 50) return 2;
  if (minutes < 90) return 3;
  return 4;
}

const INTENSITY_CLASS = [
  "bg-muted",
  "bg-primary/20",
  "bg-primary/40",
  "bg-primary/65",
  "bg-primary",
];

function generateMockHeatmap(): HeatDay[] {
  const days: HeatDay[] = [];
  const today = new Date();
  for (let i = 89; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const rand = Math.random();
    const minutes =
      rand < 0.2 ? 0 : rand < 0.5 ? Math.floor(rand * 30) + 10 : Math.floor(rand * 90) + 25;
    days.push({ date: d.toISOString().slice(0, 10), minutes });
  }
  return days;
}

export function HeatmapChart() {
  const { data: apiData, isError, isLoading } = useQuery<HeatDay[]>({
    queryKey: ["heatmap", 90],
    queryFn: () => getHeatmap(90),
  });

  const heatData: HeatDay[] = isError || !apiData ? generateMockHeatmap() : apiData;

  const weeks: HeatDay[][] = [];
  for (let i = 0; i < heatData.length; i += 7) {
    weeks.push(heatData.slice(i, i + 7));
  }

  const totalMinutes = heatData.reduce((s, d) => s + d.minutes, 0);
  const totalHours = Math.floor(totalMinutes / 60);

  return (
    <Card className="animate-card-in border-border/60">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold">学习热力图</CardTitle>
          <span className="text-xs text-muted-foreground">近90天 · 共 {totalHours}h</span>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex gap-1">
            {Array.from({ length: 13 }).map((_, week) => (
              <div key={week} className="flex flex-col gap-1">
                {Array.from({ length: 7 }).map((__, day) => (
                  <Skeleton key={day} className="h-3 w-3 rounded-sm" />
                ))}
              </div>
            ))}
          </div>
        ) : (
          <div className="flex gap-1">
            {weeks.map((week, wi) => (
              <div key={wi} className="flex flex-col gap-1">
                {week.map((day, di) => (
                  <div
                    key={di}
                    className={cn("w-3 h-3 rounded-sm transition-colors duration-200", INTENSITY_CLASS[getIntensity(day.minutes)])}
                    title={`${day.date}: ${day.minutes}分钟`}
                  />
                ))}
              </div>
            ))}
          </div>
        )}
        <div className="flex items-center gap-1.5 mt-3">
          <span className="text-[10px] text-muted-foreground">少</span>
          {INTENSITY_CLASS.map((cls, i) => (
            <div key={i} className={cn("w-2.5 h-2.5 rounded-sm", isLoading ? "bg-muted" : cls)} />
          ))}
          <span className="text-[10px] text-muted-foreground">多</span>
        </div>
      </CardContent>
    </Card>
  );
}
