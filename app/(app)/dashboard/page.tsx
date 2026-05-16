import { MasteryRing } from "@/components/dashboard/mastery-ring";
import { StatsRow } from "@/components/dashboard/stats-row";
import { TodayTasks } from "@/components/dashboard/today-tasks";
import { HeatmapChart } from "@/components/dashboard/heatmap";
import { WeeklySummary } from "@/components/dashboard/weekly-summary";
import { SubjectProgress } from "@/components/dashboard/subject-progress";

export default function DashboardPage() {
  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto space-y-5 md:space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-foreground">学习总览</h1>
        <p className="text-sm text-muted-foreground mt-0.5">今天也要加油</p>
      </div>

      {/* Top stats */}
      <StatsRow />

      {/* Main grid — stacks on mobile */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
        <div className="md:col-span-2 space-y-4 md:space-y-6">
          <TodayTasks />
          <HeatmapChart />
        </div>
        <div className="space-y-4 md:space-y-6">
          <MasteryRing />
          <SubjectProgress />
        </div>
      </div>

      {/* Weekly summary */}
      <WeeklySummary />
    </div>
  );
}
