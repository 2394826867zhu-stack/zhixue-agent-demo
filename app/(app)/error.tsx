"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, RotateCcw, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const router = useRouter();

  useEffect(() => {
    console.error("[AppError]", error);
  }, [error]);

  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <div className="flex flex-col items-center gap-5 text-center max-w-sm px-6">
        <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center">
          <AlertCircle className="text-destructive" size={30} />
        </div>
        <div>
          <h2 className="text-xl font-bold text-foreground">页面加载失败</h2>
          <p className="text-sm text-muted-foreground mt-1">
            遇到了意外错误，请重试。若问题持续请返回主页。
          </p>
        </div>
        <div className="flex gap-3">
          <Button onClick={reset} className="gap-2">
            <RotateCcw size={14} /> 重试
          </Button>
          <Button variant="outline" className="gap-2" onClick={() => router.push("/dashboard")}>
            <ArrowLeft size={14} /> 主页
          </Button>
        </div>
      </div>
    </div>
  );
}
