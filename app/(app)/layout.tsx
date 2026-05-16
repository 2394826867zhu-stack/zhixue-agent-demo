import { Sidebar } from "@/components/layout/sidebar";
import { AuthGuard } from "@/components/auth/auth-guard";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="min-h-screen flex">
        <Sidebar />
        <main className="ml-56 flex-1 min-h-screen bg-background">
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}
