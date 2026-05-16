"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, BookOpen, Brain, Layers, Target,
  AlertCircle, CheckSquare, TrendingUp, MessageCircle, LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/store";
import { TurbineLogo } from "@/components/ui/turbine-logo";

const NAV = [
  { href: "/dashboard", label: "首页", icon: LayoutDashboard },
  { href: "/notes", label: "笔记", icon: BookOpen },
  { href: "/knowledge", label: "知识点", icon: Brain },
  { href: "/flashcards", label: "闪卡复习", icon: Layers },
  { href: "/training", label: "训练", icon: Target },
  { href: "/mistakes", label: "错题本", icon: AlertCircle },
  { href: "/tasks", label: "每日任务", icon: CheckSquare },
  { href: "/progress", label: "进度", icon: TrendingUp },
  { href: "/guidance", label: "引导问答", icon: MessageCircle },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, clearAuth } = useAuthStore();

  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-sidebar border-r border-sidebar-border hidden md:flex flex-col z-40">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-sidebar-border">
        <div className="flex items-center gap-2.5">
          <TurbineLogo className="w-8 h-8 shrink-0" dark />
          <div>
            <p className="font-semibold text-sidebar-foreground text-sm leading-tight">知曜</p>
            <p className="text-[10px] text-muted-foreground leading-tight">智学Agent</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-primary"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"
              )}
            >
              <Icon size={16} strokeWidth={active ? 2.5 : 1.8} />
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
            className="text-muted-foreground hover:text-destructive transition-colors"
            title="退出登录"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}
