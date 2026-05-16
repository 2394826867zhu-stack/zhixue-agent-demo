import { Sidebar } from "@/components/layout/sidebar";
import { MobileHeader } from "@/components/layout/mobile-nav";
import { AuthGuard } from "@/components/auth/auth-guard";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="min-h-screen flex">
        <Sidebar />
        <MobileHeader />
        <main className="w-full md:ml-56 flex-1 min-h-screen bg-background pt-14 md:pt-0">
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}
