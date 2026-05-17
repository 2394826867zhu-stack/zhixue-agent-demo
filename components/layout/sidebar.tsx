"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, BookOpen, Brain, Layers, Target,
  AlertCircle, CheckSquare, TrendingUp, MessageCircle, LogOut,
  Sparkles, ArrowRight, Flame, GaugeCircle, Route, UserRound,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/store";
import { TurbineLogo } from "@/components/ui/turbine-logo";

const NAV_GROUPS = [
  {
    label: "今日",
    items: [
      { href: "/dashboard", label: "首页", icon: LayoutDashboard },
      { href: "/path", label: "学习路径", icon: Route },
      { href: "/tasks", label: "每日任务", icon: CheckSquare },
    ],
  },
  {
    label: "学习",
    items: [
      { href: "/notes", label: "笔记", icon: BookOpen },
      { href: "/knowledge", label: "知识点", icon: Brain },
      { href: "/flashcards", label: "闪卡复习", icon: Layers },
      { href: "/training", label: "训练", icon: Target },
      { href: "/mistakes", label: "错题本", icon: AlertCircle },
    ],
  },
  {
    label: "AI 与成长",
    items: [
      { href: "/guidance", label: "AI 助手", icon: MessageCircle },
      { href: "/progress", label: "成长看板", icon: TrendingUp },
      { href: "/profile", label: "个人中心", icon: UserRound },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, clearAuth } = useAuthStore();

  return (
    <aside className="fixed left-0 top-0 z-40 hidden h-full w-64 flex-col overflow-hidden border-r border-sidebar-border/80 bg-sidebar/88 shadow-[14px_0_44px_oklch(0.35_0.03_230_/_8%)] backdrop-blur-2xl md:flex">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_35%_0%,oklch(0.78_0.15_170_/_18%),transparent_36%),linear-gradient(180deg,oklch(1_0_0_/_70%),transparent_34%)]" />
      <div className="pointer-events-none absolute inset-x-4 top-24 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
      {/* Logo */}
      <div className="relative px-5 pb-4 pt-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/12 shadow-[inset_0_0_0_1px_oklch(0.70_0.16_170_/_18%),0_10px_24px_oklch(0.70_0.16_170_/_14%)]">
            <TurbineLogo className="w-7 h-7 shrink-0 text-sidebar-primary" />
          </div>
          <div>
            <p className="font-semibold text-sidebar-foreground text-sm leading-tight">知曜</p>
            <p className="text-[10px] text-sidebar-foreground/55 leading-tight">AI Learning Companion</p>
          </div>
        </div>
      </div>

      <div className="relative mx-3 rounded-[1.35rem] border border-primary/18 bg-white/58 p-3.5 shadow-[0_12px_30px_oklch(0.35_0.03_230_/_7%)] backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sidebar-primary">
            <GaugeCircle size={16} />
            <p className="text-xs font-semibold">今日节奏</p>
          </div>
          <span className="rounded-full bg-primary/12 px-2 py-0.5 text-[10px] font-bold text-primary">64%</span>
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-primary/10">
          <div className="h-full w-[64%] rounded-full bg-primary shadow-[0_0_16px_oklch(0.70_0.16_170_/_35%)]" />
        </div>
        <div className="mt-3 rounded-2xl border border-primary/12 bg-primary/7 p-3">
          <div className="flex items-center gap-2 text-sidebar-primary">
            <Sparkles size={14} />
            <p className="text-[11px] font-semibold">AI 下一步</p>
          </div>
          <p className="mt-1.5 text-[11px] leading-relaxed text-sidebar-foreground/74">
            先完成 2 个轻任务，再进入深度训练。
          </p>
          <Link href="/tasks" className="mt-2 flex items-center gap-1 text-[11px] font-semibold text-primary">
            去完成
            <ArrowRight size={12} />
          </Link>
        </div>
      </div>

      {/* Nav */}
      <nav className="relative flex-1 space-y-4 overflow-y-auto px-3 py-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="rounded-[1.25rem] border border-sidebar-border/45 bg-white/34 p-1.5 shadow-[inset_0_1px_0_oklch(1_0_0_/_55%)]">
            <p className="px-2.5 pb-1.5 pt-1 text-[11px] font-semibold tracking-wide text-sidebar-foreground/45">
              {group.label}
            </p>
            {group.items.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || pathname.startsWith(href + "/");
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "tap-feedback group relative flex items-center gap-2.5 overflow-hidden rounded-2xl px-2.5 py-2.5 text-sm font-semibold",
                    active
                      ? "bg-white/70 text-primary shadow-[inset_0_0_0_1px_oklch(0.70_0.16_170_/_18%),0_8px_20px_oklch(0.70_0.16_170_/_8%)]"
                      : "text-sidebar-foreground/72 hover:translate-x-0.5 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground"
                  )}
                >
                  <span
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-all duration-200",
                      active ? "bg-primary/10 text-primary" : "bg-white/38 text-sidebar-foreground/58 group-hover:bg-white/70 group-hover:text-sidebar-accent-foreground"
                    )}
                  >
                    <Icon
                      size={16}
                      strokeWidth={active ? 2.4 : 1.8}
                      className={cn("transition-transform duration-200 ease-out", active && "scale-105")}
                    />
                  </span>
                  <span>{label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User footer */}
      <div className="relative border-t border-sidebar-border/70 px-3 py-4">
        <div className="mb-2 flex items-center gap-2 rounded-2xl border border-amber-400/16 bg-amber-300/10 px-3 py-2 text-amber-700">
          <Flame size={14} />
          <span className="text-[11px] font-semibold">连续学习 14 天</span>
        </div>
        <div className="flex items-center gap-2 rounded-2xl border border-sidebar-border/55 bg-white/44 px-3 py-2 shadow-[inset_0_1px_0_oklch(1_0_0_/_55%)] hover:bg-sidebar-accent/70">
          <div className="w-8 h-8 rounded-full bg-sidebar-primary/15 flex items-center justify-center text-sidebar-primary text-xs font-semibold ring-1 ring-sidebar-primary/20">
            {(user?.nickname || user?.username || "U")[0].toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-sidebar-foreground truncate">
              {user?.nickname || user?.username || "用户"}
            </p>
            <p className="text-[10px] text-sidebar-foreground/45">保持轻松节奏</p>
          </div>
          <button
            onClick={clearAuth}
            className="tap-feedback rounded-lg p-1 text-muted-foreground hover:bg-destructive/8 hover:text-destructive"
            title="退出登录"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}
