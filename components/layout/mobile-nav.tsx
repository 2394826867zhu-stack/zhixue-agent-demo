"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, BookOpen, Brain, Layers, Target,
  AlertCircle, CheckSquare, TrendingUp, MessageCircle,
  LogOut, Menu, X, UserRound, Route,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/store";
import { TurbineLogo } from "@/components/ui/turbine-logo";

const NAV = [
  { href: "/dashboard", label: "首页",     icon: LayoutDashboard },
  { href: "/path",      label: "学习路径", icon: Route },
  { href: "/notes",     label: "笔记",     icon: BookOpen },
  { href: "/knowledge", label: "知识库",   icon: Brain },
  { href: "/flashcards",label: "闪卡复习", icon: Layers },
  { href: "/training",  label: "训练",     icon: Target },
  { href: "/mistakes",  label: "错题本",   icon: AlertCircle },
  { href: "/tasks",     label: "每日任务", icon: CheckSquare },
  { href: "/guidance",  label: "AI 助手", icon: MessageCircle },
  { href: "/progress",  label: "进度",     icon: TrendingUp },
  { href: "/profile",   label: "个人中心", icon: UserRound },
];

const BOTTOM_NAV = [
  { href: "/dashboard", label: "首页", icon: LayoutDashboard },
  { href: "/tasks", label: "任务", icon: CheckSquare },
  { href: "/path", label: "学习", icon: Route },
  { href: "/profile", label: "我的", icon: UserRound },
];

export function MobileHeader() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const { user, clearAuth } = useAuthStore();
  const activeIndex = Math.max(
    0,
    BOTTOM_NAV.findIndex(({ href }) => pathname === href || pathname.startsWith(href + "/"))
  );

  return (
    <>
      {/* Top bar */}
      <header className="fixed top-0 left-0 right-0 z-50 h-14 bg-sidebar border-b border-sidebar-border flex items-center px-4 gap-3 md:hidden">
        <button
          onClick={() => setOpen(true)}
          aria-label="打开侧栏导航"
          className="tap-feedback p-1.5 rounded-md text-sidebar-foreground hover:bg-sidebar-accent/60"
        >
          <Menu size={20} />
        </button>
        <div className="flex items-center gap-2">
          <TurbineLogo className="w-6 h-6 text-sidebar-primary" />
          <span className="font-semibold text-sm text-sidebar-foreground">知曜</span>
        </div>
      </header>

      <nav className="fixed bottom-[calc(0.9rem+env(safe-area-inset-bottom))] left-4 right-4 z-50 h-[4.35rem] overflow-hidden rounded-[1.65rem] border border-white/70 bg-card/82 px-2 shadow-[0_18px_48px_oklch(0.35_0.03_230_/_18%),inset_0_1px_0_oklch(1_0_0_/_70%)] backdrop-blur-2xl md:hidden">
        <div
          className="absolute bottom-2 top-2 w-[calc((100%-1rem)/4)] rounded-[1.25rem] border border-primary/14 bg-primary/12 shadow-[0_10px_24px_oklch(0.70_0.16_170_/_16%)] transition-transform duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)]"
          style={{ transform: `translateX(calc(${activeIndex} * (100% + 0.25rem)))` }}
        />
        <div className="relative grid h-full grid-cols-4">
        {BOTTOM_NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "tap-feedback relative flex flex-col items-center justify-center gap-0.5 rounded-xl text-[11px] font-semibold",
                active ? "text-primary" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <span
                className={cn(
                  "absolute top-1 h-1 w-1 rounded-full bg-primary transition-opacity duration-200",
                  active ? "opacity-100" : "opacity-0"
                )}
              />
              <Icon
                size={19}
                strokeWidth={active ? 2.4 : 1.8}
                className={cn("transition-transform duration-200 ease-out", active && "-translate-y-0.5 scale-105")}
              />
              {label}
            </Link>
          );
        })}
        </div>
      </nav>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/50 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Drawer */}
      <aside
        className={cn(
          "fixed top-0 left-0 h-full w-64 z-50 bg-sidebar border-r border-sidebar-border flex flex-col transition-transform duration-300 ease-in-out md:hidden",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-sidebar-border flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <TurbineLogo className="w-8 h-8 shrink-0 text-sidebar-primary" />
            <div>
          <p className="font-semibold text-sidebar-foreground text-sm leading-tight">知曜</p>
          <p className="text-[10px] text-sidebar-foreground/55 leading-tight">AI Learning Companion</p>
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="关闭侧栏导航"
            className="tap-feedback p-1.5 rounded-md text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
          >
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={cn(
                  "tap-feedback relative flex items-center gap-3 overflow-hidden px-3 py-2.5 rounded-xl text-sm font-medium",
                  active
                    ? "bg-white/70 text-sidebar-primary shadow-[inset_0_0_0_1px_oklch(0.70_0.16_170_/_14%)]"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/60"
                )}
              >
                <Icon size={16} strokeWidth={active ? 2.5 : 1.8} className={cn(active && "scale-105")} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* User footer */}
        <div className="px-3 py-4 border-t border-sidebar-border">
          <div className="flex items-center gap-2 px-3 py-2">
            <div className="w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center text-primary text-xs font-semibold">
              {(user?.nickname || user?.username || "U")[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-sidebar-foreground truncate">
                {user?.nickname || user?.username || "用户"}
              </p>
            </div>
            <button
              onClick={clearAuth}
              aria-label="退出登录"
              className="tap-feedback rounded-lg p-1 text-muted-foreground hover:bg-destructive/8 hover:text-destructive"
              title="退出登录"
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
