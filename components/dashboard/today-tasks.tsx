"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CheckCircle2, Circle, Layers, AlertCircle, PenLine, Sparkles, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { getTodayTasks, updateTask, generateTasks } from "@/lib/api";

interface Task {
  id: string;
  title: string;
  task_type: string;
  subject?: string;
  estimated_minutes?: number;
  priority?: string;
  status?: string;
  is_done: boolean;
}

const TYPE_ICON: Record<string, React.ElementType> = {
  flashcard_review: Layers,
  mistake_review: AlertCircle,
  manual: PenLine,
};

const PRIORITY_COLOR: Record<string, string> = {
  high: "text-rose-500",
  medium: "text-amber-500",
  normal: "text-amber-500",
  low: "text-slate-400",
};

// Fallback mock data while API is loading
const MOCK_TASKS: Task[] = [
  { id: "1", title: "复习数学闪卡（12张）", task_type: "flashcard_review", subject: "数学", estimated_minutes: 24, priority: "high", is_done: false },
  { id: "2", title: "错题重练·物理（3题）", task_type: "mistake_review", subject: "物理", estimated_minutes: 15, priority: "high", is_done: false },
  { id: "3", title: "复习英语闪卡（8张）", task_type: "flashcard_review", subject: "英语", estimated_minutes: 16, priority: "normal", is_done: true },
  { id: "4", title: "背高考化学方程式", task_type: "manual", subject: "化学", estimated_minutes: 25, priority: "normal", is_done: false },
];

export function TodayTasks() {
  const queryClient = useQueryClient();

  const { data: apiTasks, isLoading, isError } = useQuery<Task[]>({
    queryKey: ["today-tasks"],
    queryFn: getTodayTasks,
  });

  const tasks: Task[] = isError || (!isLoading && !apiTasks) ? MOCK_TASKS : (apiTasks ?? []);

  const toggleMutation = useMutation({
    mutationFn: ({ id, isDone }: { id: string; isDone: boolean }) =>
      updateTask(id, { status: isDone ? "done" : "pending" }),
    onMutate: async ({ id, isDone }) => {
      // Optimistic update
      await queryClient.cancelQueries({ queryKey: ["today-tasks"] });
      queryClient.setQueryData<Task[]>(["today-tasks"], (old) =>
        old?.map((t) => (t.id === id ? { ...t, is_done: isDone, status: isDone ? "done" : "pending" } : t)) ?? []
      );
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ["today-tasks"] });
    },
  });

  const generateMutation = useMutation({
    mutationFn: generateTasks,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["today-tasks"] });
    },
  });

  const done = tasks.filter((t) => t.is_done).length;
  const total = tasks.length;

  return (
    <Card className="animate-card-in border-border/60">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold">今日任务</CardTitle>
          <div className="flex items-center gap-2">
            {isLoading ? (
              <Loader2 size={13} className="animate-spin text-muted-foreground" />
            ) : (
              <span className="text-xs text-muted-foreground">{done}/{total} 完成</span>
            )}
            <button
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
              className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors disabled:opacity-50"
            >
              {generateMutation.isPending ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Sparkles size={12} />
              )}
              AI生成
            </button>
          </div>
        </div>
        {/* Progress bar */}
        <div className="h-1 bg-muted rounded-full mt-2">
          <div
            className="h-1 bg-primary rounded-full transition-all duration-500"
            style={{ width: total > 0 ? `${(done / total) * 100}%` : "0%" }}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-1">
        {isLoading && tasks.length === 0 && (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="flex items-center gap-3 rounded-lg px-3 py-2.5">
                <Skeleton className="h-4 w-4 rounded-full" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-5 w-10 rounded-full" />
              </div>
            ))}
          </div>
        )}

        {!isLoading && tasks.map((task, index) => {
          const Icon = TYPE_ICON[task.task_type] || PenLine;
          const priority = task.priority ?? "normal";
          return (
            <div
              key={task.id}
              className={cn(
                "tap-feedback flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer group",
                task.is_done ? "opacity-55" : "hover:bg-muted/60"
              )}
              style={{ animationDelay: `${index * 35}ms` }}
              onClick={() =>
                toggleMutation.mutate({ id: task.id, isDone: !task.is_done })
              }
            >
              {task.is_done ? (
                <CheckCircle2 size={16} className="text-primary shrink-0 transition-transform duration-200 group-active:scale-90" />
              ) : (
                <Circle size={16} className="text-muted-foreground group-hover:text-primary transition-colors shrink-0 group-active:scale-90" />
              )}
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <Icon size={13} className={cn("shrink-0", PRIORITY_COLOR[priority])} />
                <span className={cn("text-sm truncate", task.is_done && "line-through text-muted-foreground")}>
                  {task.title}
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {task.subject && (
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                    {task.subject}
                  </Badge>
                )}
                {task.estimated_minutes && (
                  <span className="text-[10px] text-muted-foreground">
                    {task.estimated_minutes}min
                  </span>
                )}
              </div>
            </div>
          );
        })}

        {!isLoading && tasks.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            今天没有任务，点击 AI生成 创建
          </p>
        )}
      </CardContent>
    </Card>
  );
}
