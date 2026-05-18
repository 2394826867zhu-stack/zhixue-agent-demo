import { Sidebar } from "@/components/layout/sidebar";
import { MobileHeader } from "@/components/layout/mobile-nav";
import { AuthGuard } from "@/components/auth/auth-guard";
import { PageTransition } from "@/components/layout/page-transition";
import { ShellBackground } from "@/components/layout/shell-background";
import { GoalDialog } from "@/components/onboarding/goal-dialog";
import { AgentLayer } from "@/components/agent/agent-layer";
import { OnboardingGate } from "@/components/onboarding/onboarding-gate";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="min-h-screen flex">
        <ShellBackground />
        <Sidebar />
        <MobileHeader />
        <OnboardingGate />
        <GoalDialog />
        <AgentLayer />
        <main className="w-full md:ml-64 flex-1 min-h-screen bg-transparent pt-14 pb-24 md:pt-0 md:pb-0">
          <PageTransition>{children}</PageTransition>
        </main>
      </div>
    </AuthGuard>
  );
}
