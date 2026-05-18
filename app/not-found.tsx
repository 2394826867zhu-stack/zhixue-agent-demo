import Link from "next/link";
import { Home, BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-6 text-center max-w-sm px-6">
        <div className="text-[6rem] font-bold leading-none text-primary/15 select-none">
          404
        </div>
        <div>
          <h2 className="text-2xl font-bold text-foreground">页面不存在</h2>
          <p className="text-sm text-muted-foreground mt-2">
            你访问的页面不存在或已被移除，请检查链接是否正确。
          </p>
        </div>
        <div className="flex gap-3">
          <Button asChild className="gap-2">
            <Link href="/dashboard">
              <Home size={14} /> 回主页
            </Link>
          </Button>
          <Button asChild variant="outline" className="gap-2">
            <Link href="/notes">
              <BookOpen size={14} /> 去笔记
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
