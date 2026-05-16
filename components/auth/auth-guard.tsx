"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { Loader2 } from "lucide-react";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { token } = useAuthStore();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // Give Zustand persist a tick to rehydrate from localStorage
    const stored = localStorage.getItem("access_token");
    if (!stored && !token) {
      router.replace("/login");
    } else {
      setChecked(true);
    }
  }, [router, token]);

  if (!checked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="text-primary animate-spin" size={28} />
      </div>
    );
  }

  return <>{children}</>;
}
