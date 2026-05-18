"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BookOpenCheck, CalendarDays, CheckCircle2, FileText, Loader2, RotateCcw, Send, Sparkles, Target, UploadCloud } from "lucide-react";
import { AgentOrb } from "@/components/agent/agent-orb";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { TurbineLogo } from "@/components/ui/turbine-logo";
import { getOnboardingStatus, restartOnboarding, sendOnboardingMessage, type OnboardingDraft, type OnboardingStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

type ChatItem = {
  id: string;
  role: "agent" | "user" | "system";
  content: string;
};

const STEP_LABEL: Record<string, string> = {
  grade: "年级",
  subjects: "主攻科目",
  progress: "学习进度",
  performance: "成绩水平",
  next_exam: "目标考试",
  goal: "学习目标",
  upload: "资料补充",
  confirm: "确认建档",
  completed: "已完成",
};

const STEP_SUGGESTIONS: Record<string, string[]> = {
  grade: ["初一", "初二", "初三", "高一", "高二", "高三"],
  subjects: ["数学、物理、英语", "语文、数学、英语", "全科都需要", "先管理薄弱科目"],
  progress: ["数学二次函数，物理浮力", "英语 Unit 4，化学酸碱盐", "我不确定，稍后上传课程表"],
  performance: ["班级前 20%", "中等偏上", "中等", "比较吃力"],
  next_exam: ["期末考试，6月25日", "一模，6月12日", "月考，下周五", "暂时不清楚"],
  goal: ["稳定完成作业和复习", "把数学提上去", "冲刺重点高中", "减少学习焦虑"],
  upload: ["先跳过", "我会上传课程表", "我会上传成绩单", "我会上传考试安排"],
  confirm: ["确认建立学习系统", "我想修改前面信息"],
};

function readDraftValue(draft: OnboardingDraft, key: string) {
  const value = draft[key];
  if (!value) return "待收集";
  if (Array.isArray(value)) return value.join("、");
  if (typeof value === "object") return Object.entries(value as Record<string, string>).map(([k, v]) => `${k}: ${v}`).join("；");
  return String(value);
}

function ProfileDraftPanel({ status }: { status?: OnboardingStatus }) {
  const draft = status?.profile_draft ?? {};
  const items = [
    { label: "当前年级", value: readDraftValue(draft, "grade"), icon: BookOpenCheck },
    { label: "主攻科目", value: readDraftValue(draft, "subjects"), icon: Sparkles },
    { label: "学习进度", value: readDraftValue(draft, "progress"), icon: FileText },
    { label: "成绩水平", value: readDraftValue(draft, "performance"), icon: Target },
    { label: "考试时间线", value: draft.next_exam_name ? `${draft.next_exam_name}${draft.next_exam_date ? ` · ${draft.next_exam_date}` : ""}` : "待收集", icon: CalendarDays },
    { label: "长期目标", value: readDraftValue(draft, "goal"), icon: Target },
  ];

  return (
    <Card className="border-white/70 bg-card/82 backdrop-blur-xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <TurbineLogo className="h-5 w-5 text-primary" />
          学习档案草稿
        </CardTitle>
        <p className="text-sm text-muted-foreground">AI 会把这些信息整理成知识库、考试时间线和第一周计划。</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map(({ label, value, icon: Icon }) => (
          <div key={label} className="rounded-2xl border border-border/70 bg-background/70 p-3">
            <div className="mb-1 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
              <Icon size={13} className="text-primary" />
              {label}
            </div>
            <p className={cn("text-sm font-medium leading-relaxed", value === "待收集" ? "text-muted-foreground" : "text-foreground")}>{value}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function BuildComplete({ status }: { status?: OnboardingStatus }) {
  const draft = status?.profile_draft ?? {};
  return (
    <Card className="animate-card-in border-primary/20 bg-gradient-to-br from-primary/12 via-card to-card">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-primary text-primary-foreground">
            <CheckCircle2 size={22} />
          </div>
          <div>
            <CardTitle>学习系统已建立</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">知曜会从今天开始维护你的知识库、目标和复习节奏。</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-3">
        {[
          { label: "当前阶段", value: readDraftValue(draft, "grade") },
          { label: "目标考试", value: draft.next_exam_name ? String(draft.next_exam_name) : "已记录" },
          { label: "今日建议", value: "回家后告诉 AI 今天学了什么" },
        ].map((item) => (
          <div key={item.label} className="rounded-2xl border border-border/70 bg-card/78 p-4">
            <p className="text-xs font-semibold text-muted-foreground">{item.label}</p>
            <p className="mt-1 text-sm font-bold text-foreground">{item.value}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatItem[]>([]);

  const { data: status, isLoading } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: () => getOnboardingStatus(),
    retry: false,
  });

  useEffect(() => {
    if (status?.question && messages.length === 0) {
      queueMicrotask(() => setMessages([{ id: "initial", role: "agent", content: status.question }]));
    }
  }, [messages.length, status?.question]);

  const progress = useMemo(() => {
    if (!status) return 0;
    return Math.min(100, Math.round((status.step_index / status.total_steps) * 100));
  }, [status]);

  const currentStep = status?.current_step ?? "grade";
  const suggestions = STEP_SUGGESTIONS[currentStep] ?? [];

  const sendMutation = useMutation({
    mutationFn: (message: string) => sendOnboardingMessage(message),
    onSuccess: (next) => {
      setMessages((prev) => [
        ...prev.filter((item) => item.id !== "thinking"),
        { id: `agent-${Date.now()}`, role: "agent", content: next.reply },
      ]);
      queryClient.setQueryData(["onboarding-status"], {
        current_step: next.step,
        step_index: next.step_index,
        total_steps: next.total_steps,
        completed: next.completed,
        question: next.reply,
        profile_draft: next.profile_draft,
      });
      if (next.completed) {
        try {
          localStorage.setItem("zhiyao_onboarding_completed", "true");
          localStorage.removeItem("zhiyao_needs_onboarding");
        } catch {}
      }
    },
    onError: () => {
      setMessages((prev) => [
        ...prev.filter((item) => item.id !== "thinking"),
        { id: `agent-error-${Date.now()}`, role: "agent", content: "我刚才没有保存成功。请再发一次，或者稍后重试。" },
      ]);
    },
  });

  const restartMutation = useMutation({
    mutationFn: () => restartOnboarding(),
    onSuccess: (next) => {
      setMessages([{ id: "restart", role: "agent", content: next.question }]);
      queryClient.setQueryData(["onboarding-status"], next);
    },
  });

  function submit(text = input) {
    const content = text.trim();
    if (!content || sendMutation.isPending) return;
    setInput("");
    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: "user", content },
      { id: "thinking", role: "system", content: "正在更新你的学习档案..." },
    ]);
    sendMutation.mutate(content);
  }

  return (
    <div className="relative min-h-dvh overflow-hidden bg-background px-4 py-5 md:px-8 md:py-8">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_18%_10%,oklch(0.82_0.14_170_/_20%),transparent_34%),radial-gradient(circle_at_88%_18%,oklch(0.76_0.13_285_/_14%),transparent_28%)]" />
      <header className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary text-primary-foreground shadow-sm">
            <TurbineLogo className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-bold text-foreground">知曜建档向导</p>
            <p className="text-xs text-muted-foreground">先建立学习系统，再进入每日陪伴</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="gap-2" onClick={() => restartMutation.mutate()} disabled={restartMutation.isPending}>
          <RotateCcw size={14} />
          重新填写
        </Button>
      </header>

      <main className="mx-auto mt-6 grid max-w-7xl gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <section className="overflow-hidden rounded-[2rem] border border-white/70 bg-card/82 shadow-[var(--shadow-card)] backdrop-blur-xl">
          <div className="border-b border-border/65 p-5 md:p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <Badge variant="secondary" className="bg-primary/10 text-primary">
                  {STEP_LABEL[currentStep] ?? "建档中"}
                </Badge>
                <h1 className="mt-3 text-2xl font-bold text-foreground md:text-3xl">让 AI 先认识你的学习现场</h1>
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                  这些信息会帮助知曜建立基础知识库、考试时间线和第一周计划。关键问题需要回答，资料上传可以稍后补充。
                </p>
              </div>
              <div className="flex items-center gap-3">
                <AgentOrb thinking={sendMutation.isPending || isLoading} active className="h-16 w-16" />
                <div className="min-w-32">
                  <p className="text-xs font-semibold text-muted-foreground">建档进度</p>
                  <p className="mt-1 text-2xl font-bold text-foreground">{progress}%</p>
                </div>
              </div>
            </div>
            <Progress value={progress} className="mt-5 h-2" />
          </div>

          <div className="space-y-4 p-4 md:p-6">
            {status?.completed && <BuildComplete status={status} />}
            <div className="max-h-[48dvh] space-y-3 overflow-y-auto pr-1">
              {messages.map((message) => (
                <div key={message.id} className={cn("flex", message.role === "user" && "justify-end")}>
                  <div
                    className={cn(
                      "max-w-[88%] rounded-3xl px-4 py-3 text-sm leading-relaxed",
                      message.role === "user"
                        ? "bg-primary text-primary-foreground rounded-br-md"
                        : message.role === "system"
                          ? "border border-primary/18 bg-primary/8 text-primary"
                          : "border border-border/70 bg-background/82 text-foreground rounded-bl-md"
                    )}
                  >
                    {message.role === "system" && <Loader2 size={14} className="mr-2 inline animate-spin align-middle" />}
                    {message.content}
                  </div>
                </div>
              ))}
            </div>

            {!status?.completed && (
              <div className="rounded-[1.6rem] border border-border/75 bg-background/80 p-3">
                <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
                  {suggestions.map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => submit(item)}
                      className="shrink-0 rounded-full border border-border bg-card px-3 py-2 text-xs font-medium text-muted-foreground transition hover:border-primary/35 hover:text-primary"
                    >
                      {item}
                    </button>
                  ))}
                </div>
                <div className="flex items-end gap-2">
                  <button className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl text-muted-foreground hover:bg-muted" aria-label="上传资料">
                    <UploadCloud size={19} />
                  </button>
                  <textarea
                    rows={1}
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        submit();
                      }
                    }}
                    placeholder="直接回答 AI 的问题，也可以粘贴课程表、成绩单文字..."
                    className="max-h-32 min-h-11 flex-1 resize-none bg-transparent px-1 py-3 text-sm outline-none placeholder:text-muted-foreground"
                  />
                  <Button size="icon" className="h-11 w-11 rounded-2xl" onClick={() => submit()} disabled={!input.trim() || sendMutation.isPending} aria-label="发送">
                    {sendMutation.isPending ? <Loader2 size={17} className="animate-spin" /> : <Send size={17} />}
                  </Button>
                </div>
              </div>
            )}

            {status?.completed && (
              <div className="flex flex-col gap-3 sm:flex-row">
                <Button size="lg" className="gap-2" onClick={() => router.replace("/dashboard")}>
                  进入我的学习系统
                  <ArrowRight size={16} />
                </Button>
                <Button size="lg" variant="outline" onClick={() => router.replace("/path")}>
                  查看 AI 学习路径
                </Button>
              </div>
            )}
          </div>
        </section>

        <aside className="space-y-5">
          <ProfileDraftPanel status={status} />
          <Card className="border-primary/18 bg-gradient-to-br from-primary/10 via-card to-card">
            <CardHeader>
              <CardTitle className="text-base">建档后会发生什么</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              {["建立已学与正在学的知识库", "整理下一次考试时间线和目标", "生成第一周轻量学习计划", "之后每天只需告诉 AI 今天学了什么"].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <CheckCircle2 size={15} className="text-primary" />
                  <span>{item}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </aside>
      </main>
    </div>
  );
}
