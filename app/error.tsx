"use client";

import { useEffect } from "react";
import { AlertCircle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[GlobalError]", error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-5 text-center max-w-sm px-6">
        <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center">
          <AlertCircle className="text-destructive" size={30} />
        </div>
        <div>
          <h2 className="text-xl font-bold text-foreground">页面出错了</h2>
          <p className="text-sm text-muted-foreground mt-1">
            遇到了意外错误，请尝试刷新页面。若反复出现请联系我们。
          </p>
        </div>
        <div className="flex gap-3">
          <Button onClick={reset} className="gap-2">
            <RotateCcw size={14} /> 重试
          </Button>
          <Button variant="outline" onClick={() => (window.location.href = "/dashboard")}>
            返回主页
          </Button>
        </div>
      </div>
    </div>
  );
}
