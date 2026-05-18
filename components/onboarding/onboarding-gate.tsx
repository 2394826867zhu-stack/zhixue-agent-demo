"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

export function OnboardingGate() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    queueMicrotask(() => {
      try {
        const needsOnboarding = localStorage.getItem("zhiyao_needs_onboarding") === "true";
        const completed = localStorage.getItem("zhiyao_onboarding_completed") === "true";
        if (needsOnboarding && !completed && pathname !== "/onboarding") {
          router.replace("/onboarding");
        }
      } catch {
        // Storage can be restricted in preview surfaces; keep the app usable.
      }
    });
  }, [pathname, router]);

  return null;
}
