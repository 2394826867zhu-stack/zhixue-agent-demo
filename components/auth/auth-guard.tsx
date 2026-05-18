"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { isDemoMode } from "@/lib/api";
import { Loader2 } from "lucide-react";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { token } = useAuthStore();
  const [mounted, setMounted] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    queueMicrotask(() => setMounted(true));
  }, []);

  useEffect(() => {
    if (!mounted) return;

    const demoMode = isDemoMode();
    if (demoMode) {
      queueMicrotask(() => setChecked(true));
      return;
    }

    // Give Zustand persist a tick to rehydrate from localStorage
    const stored = (() => {
      try {
        return localStorage.getItem("access_token");
      } catch {
        return null;
      }
    })();

    if (!stored && !token) {
      router.replace("/login");
    } else {
      queueMicrotask(() => setChecked(true));
    }
  }, [mounted, router, token]);

  if (!mounted || !checked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="text-primary animate-spin" size={28} />
      </div>
    );
  }

  return <>{children}</>;
}
