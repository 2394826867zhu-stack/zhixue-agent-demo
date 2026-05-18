"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  Circle,
  Clock,
  Lock,
  Map,
  Play,
  RefreshCw,
  Route,
  Sparkles,
  Trophy,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  completePathNode,
  generatePath,
  getCoachTip,
  getPathStages,
  type PathNode,
  type PathStage,
} from "@/lib/api";

const NODE_ICON = {
  lesson: Map,
  review: RefreshCw,
  training: Play,
  project: Trophy,
};

const STATUS_STYLE: Record<PathNode["status"], string> = {
  done: "border-primary/25 bg-primary/10 text-primary",
  current: "border-sky-400/25 bg-sky-400/10 text-sky-700",
  review: "border-amber-400/25 bg-amber-400/10 text-amber-700",
  locked: "border-border bg-muted/50 text-muted-foreground",
};

function statusLabel(status: PathNode["status"]) {
  if (status === "done") return "已完成";
  if (status === "current") return "当前";
  if (status === "review") return "复习";
  return "锁定";
}

function NodeStatusIcon({ status }: { status: PathNode["status"] }) {
  if (status === "done") return <CheckCircle2 size={17} className="text-primary" />;
  if (status === "locked") return <Lock size={16} className="text-muted-foreground" />;
  return <Circle size={16} className={status === "current" ? "text-sky-600" : "text-amber-600"} />;
}

function PathNodeCard({
  node,
  onComplete,
  pending,
}: {
  node: PathNode;
  onComplete: (node: PathNode) => void;
  pending: boolean;
}) {
  const Icon = NODE_ICON[node.node_type] ?? Map;
  const actionable = node.status === "current" || node.status === "review";

  return (
    <div className="relative pl-8">
      <div className="absolute left-[0.35rem] top-0 flex h-10 w-10 -translate-x-1/2 items-center justify-center rounded-2xl border border-border/70 bg-card shadow-sm">
        <NodeStatusIcon status={node.status} />
      </div>
      <Card
        size="sm"
        className={cn(
          "tap-feedback border-border/70 bg-card/88",
          actionable && "hover:border-primary/35 hover:shadow-[var(--shadow-card-hover)]",
          node.status === "locked" && "opacity-70"
        )}
      >
        <CardContent className="space-y-3 py-1">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 gap-3">
              <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border", STATUS_STYLE[node.status])}>
                <Icon size={17} />
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary" className="h-6">{statusLabel(node.status)}</Badge>
                  {node.subject && <span className="text-xs font-medium text-muted-foreground">{node.subject}</span>}
                </div>
                <h3 className="mt-2 text-base font-semibold leading-snug text-foreground">{node.title}</h3>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1 text-xs font-medium text-muted-foreground">
              <Clock size={13} />
              {node.estimated_minutes}min
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/65 pt-3">
            <div className="min-w-0">
              <p className="text-xs font-medium text-muted-foreground">
                {node.reward ? `完成奖励：${node.reward}` : "完成后自动更新路径进度"}
              </p>
            </div>
            {actionable && (
              <Button
                variant={node.status === "current" ? "default" : "outline"}
                size="sm"
                onClick={() => onComplete(node)}
                disabled={pending}
                className="gap-1.5"
              >
                {node.status === "current" ? "完成节点" : "标记复习"}
                <ArrowRight size={14} />
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function PathPage() {
  const queryClient = useQueryClient();
  const [goal, setGoal] = useState("备战期末考试");

  const { data: stages = [], isLoading } = useQuery<PathStage[]>({
    queryKey: ["path-stages"],
    queryFn: getPathStages,
  });

  const { data: coachTip } = useQuery({
    queryKey: ["path-coach-tip"],
    queryFn: getCoachTip,
  });

  const completeMutation = useMutation({
    mutationFn: (node: PathNode) => completePathNode(node.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["path-stages"] });
      queryClient.invalidateQueries({ queryKey: ["path-coach-tip"] });
    },
  });

  const generateMutation = useMutation({
    mutationFn: () => generatePath({ goal }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["path-stages"] });
      queryClient.invalidateQueries({ queryKey: ["path-coach-tip"] });
    },
  });

  const allNodes = useMemo(() => stages.flatMap((stage) => stage.nodes), [stages]);
  const doneCount = allNodes.filter((node) => node.status === "done").length;
  const totalCount = allNodes.length;
  const currentNode = allNodes.find((node) => node.status === "current") ?? allNodes.find((node) => node.status === "review");
  const totalMinutes = allNodes.reduce((sum, node) => sum + node.estimated_minutes, 0);

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
      <section className="overflow-hidden rounded-[1.75rem] border border-border/75 bg-card/92 shadow-[var(--shadow-card)]">
        <div className="grid gap-6 p-5 lg:grid-cols-[1.25fr_0.75fr] md:p-7">
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="bg-primary/10 text-primary">
                AI 学习路径
              </Badge>
              <Badge variant="outline">{totalCount} 个节点</Badge>
            </div>
            <div className="max-w-2xl">
              <h1 className="text-2xl font-bold tracking-normal text-foreground md:text-3xl">
                把目标拆成一条今天能开始的成长路线
              </h1>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground md:text-base">
                知曜会根据知识点、错题、闪卡和考试目标，持续重排下一步学习节点。
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="relative flex-1">
                <Sparkles size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-primary" />
                <input
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  className="h-11 w-full rounded-2xl border border-border bg-background/80 pl-9 pr-3 text-sm font-medium outline-none transition focus:border-primary/45 focus:ring-4 focus:ring-primary/15"
                  placeholder="输入目标，例如：备战期末考试"
                />
              </div>
              <Button
                size="lg"
                className="gap-2"
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending || !goal.trim()}
              >
                <RefreshCw size={16} className={cn(generateMutation.isPending && "animate-spin")} />
                AI 重排路径
              </Button>
            </div>
          </div>

          <div className="rounded-3xl border border-primary/18 bg-gradient-to-br from-primary/12 via-card to-card p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-foreground">路径总进度</p>
                <p className="mt-1 text-xs text-muted-foreground">已完成 {doneCount} / {totalCount} 个节点</p>
              </div>
              <div className="rounded-2xl bg-primary/10 p-2 text-primary">
                <Route size={20} />
              </div>
            </div>
            <div className="mt-6">
              <div className="flex items-end justify-between">
                <p className="text-4xl font-bold text-foreground">
                  {totalCount ? Math.round((doneCount / totalCount) * 100) : 0}%
                </p>
                <p className="text-xs font-medium text-muted-foreground">约 {totalMinutes} 分钟</p>
              </div>
              <Progress value={totalCount ? (doneCount / totalCount) * 100 : 0} className="mt-3 h-2.5" />
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <main className="space-y-6">
          {isLoading ? (
            Array.from({ length: 3 }).map((_, index) => (
              <Card key={index}>
                <CardHeader>
                  <Skeleton className="h-5 w-40" />
                  <Skeleton className="mt-2 h-4 w-72" />
                </CardHeader>
                <CardContent className="space-y-4">
                  <Skeleton className="h-28 rounded-2xl" />
                  <Skeleton className="h-28 rounded-2xl" />
                </CardContent>
              </Card>
            ))
          ) : stages.length > 0 ? (
            stages.map((stage) => (
              <Card key={stage.id} className="animate-card-in border-border/70 bg-card/88">
                <CardHeader>
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <CardTitle>{stage.title}</CardTitle>
                        {stage.is_ai_generated && <Badge variant="secondary">AI 生成</Badge>}
                      </div>
                      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{stage.description}</p>
                    </div>
                    <div className="min-w-32">
                      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                        <span>阶段进度</span>
                        <span>{Math.round(stage.progress * 100)}%</span>
                      </div>
                      <Progress value={stage.progress * 100} className="h-2" />
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="relative space-y-4 before:absolute before:left-[0.35rem] before:top-3 before:h-[calc(100%-1.5rem)] before:w-px before:bg-border">
                    {stage.nodes.map((node) => (
                      <PathNodeCard
                        key={node.id}
                        node={node}
                        onComplete={(item) => completeMutation.mutate(item)}
                        pending={completeMutation.isPending}
                      />
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))
          ) : (
            <Card className="animate-card-in border-primary/18 bg-gradient-to-br from-primary/10 via-card to-card">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="rounded-2xl bg-primary/10 p-3 text-primary">
                    <Route size={22} />
                  </div>
                  <div>
                    <CardTitle>还没有生成学习路径</CardTitle>
                    <p className="mt-1 text-sm text-muted-foreground">
                      输入一个近期目标，知曜会先给你生成一条可执行的轻量路线。
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 sm:flex-row">
                <Button
                  className="gap-2"
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending || !goal.trim()}
                >
                  <Sparkles size={16} />
                  生成第一版路径
                </Button>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  后续可以根据错题、闪卡复习和考试目标继续微调，不需要一次规划到完美。
                </p>
              </CardContent>
            </Card>
          )}
        </main>

        <aside className="space-y-5">
          <Card className="border-primary/18 bg-gradient-to-br from-primary/10 via-card to-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles size={17} className="text-primary" />
                AI 路径教练
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm leading-relaxed text-foreground">
                {coachTip?.message ?? "正在读取你的路径建议..."}
              </p>
              {currentNode && (
                <div className="rounded-2xl border border-primary/15 bg-primary/8 p-3">
                  <p className="text-xs font-semibold text-primary">建议先做</p>
                  <p className="mt-1 text-sm font-semibold text-foreground">{currentNode.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{currentNode.estimated_minutes} 分钟 · {currentNode.subject ?? "综合"}</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">路径规则</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>完成当前节点后，后续节点会根据掌握度自动解锁或进入复习。</p>
              <p>如果目标变化，可以让 AI 重新生成路径，不会清空已完成记录。</p>
              <p>路径会优先安排到期闪卡、错题重练和薄弱知识点。</p>
            </CardContent>
          </Card>
        </aside>
      </section>
    </div>
  );
}
