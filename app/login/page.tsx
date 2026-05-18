"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/lib/store";
import { getMe, login, register } from "@/lib/api";
import { normalizeLoginIdentity } from "@/lib/auth-identity";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Loader2, Eye, EyeOff, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Dev mock — 后端未启动时直接绕过
  const DEV_USER = "demo";
  const DEV_PASS = "zhiyao2025";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    setLoading(true);
    setError("");

    // 1. Dev bypass：优先尝试真实后端，获取真实 JWT
    if (username === DEV_USER && password === DEV_PASS) {
      await new Promise((r) => setTimeout(r, 400));
      const DEV_EMAIL = "devtest@example.com";
      const DEV_PASSWORD = "ZhiYao2025Dev!";
      try {
        // 清除旧 demo 状态，确保 isDemoMode() 返回 false，login/register 才能真正访问后端
        try {
          localStorage.removeItem("access_token");
          localStorage.removeItem("zhiyao_demo_mode");
          localStorage.removeItem("zhiyao-auth");
        } catch { /* restricted surface */ }
        let loginData;
        try {
          loginData = await login({ email: DEV_EMAIL, password: DEV_PASSWORD });
        } catch {
          await register({ email: DEV_EMAIL, nickname: "知曜测试账号", password: DEV_PASSWORD });
          loginData = await login({ email: DEV_EMAIL, password: DEV_PASSWORD });
        }
        const token = loginData.access_token ?? loginData.token;
        try {
          localStorage.setItem("access_token", token);
          localStorage.removeItem("zhiyao_demo_mode");
        } catch { /* restricted surface */ }
        const user = loginData.user ?? await getMe().catch(() => ({ id: "", username: DEV_USER, nickname: "知曜测试账号" }));
        setAuth(user, token);
        router.replace("/dashboard");
      } catch {
        // 后端不可用时降级为纯 demo 模式
        try {
          localStorage.setItem("zhiyao_demo_mode", "true");
        } catch { /* restricted surface */ }
        setAuth({ id: "dev-001", username: DEV_USER, nickname: "Demo用户" }, "dev-token");
        router.replace("/dashboard");
      }
      setLoading(false);
      return;
    }

    // 2. 正式登录：调用真实后端
    try {
      try {
        localStorage.removeItem("zhiyao_demo_mode");
        localStorage.removeItem("zhiyao-auth");
      } catch {
        // Ignore storage failures in restricted preview surfaces.
      }
      const data = await login({ email: normalizeLoginIdentity(username), password });
      const token = data.access_token ?? data.token;
      try {
        localStorage.setItem("access_token", token);
      } catch {
        // Zustand state still keeps the token when storage is restricted.
      }
      const user = data.user ?? await getMe().catch(() => ({ id: "", username, nickname: username }));
      setAuth(user, token);
      router.replace("/dashboard");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "用户名或密码错误";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-primary-foreground font-bold text-xl mx-auto">
            知
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">欢迎回来</h1>
            <p className="text-sm text-muted-foreground">登录知曜 · 智学Agent</p>
          </div>
        </div>

        {/* Form */}
        <Card>
          <CardContent className="py-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Username */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground" htmlFor="username">
                  用户名
                </label>
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="输入用户名"
                  className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground" htmlFor="password">
                  密码
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPwd ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="输入密码"
                    className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 pr-10 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd((s) => !s)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/8 border border-destructive/20 rounded-lg px-3 py-2.5">
                  <AlertCircle size={14} />
                  {error}
                </div>
              )}

              {/* Submit */}
              <Button
                type="submit"
                disabled={!username.trim() || !password.trim() || loading}
                size="lg"
                className="w-full gap-2 mt-1"
              >
                {loading && <Loader2 size={15} className="animate-spin" />}
                {loading ? "登录中…" : "登录"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Register link */}
        <p className="text-center text-sm text-muted-foreground">
          还没有账号？{" "}
          <Link href="/register" className="text-primary hover:underline font-medium">
            立即注册
          </Link>
        </p>
      </div>
    </div>
  );
}
