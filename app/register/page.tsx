"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/lib/store";
import { register, login } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Loader2, Eye, EyeOff, AlertCircle, CheckCircle2 } from "lucide-react";
import { SpiralLogo } from "@/components/ui/spiral-logo";

const GRADES = ["初一", "初二", "初三", "高一", "高二", "高三", "大一", "大二", "大三", "大四", "其他"];

function PasswordStrength({ pwd }: { pwd: string }) {
  const checks = [pwd.length >= 8, /[A-Z]/.test(pwd), /[0-9]/.test(pwd)];
  const score = checks.filter(Boolean).length;
  const colors = ["bg-muted", "bg-red-400", "bg-amber-400", "bg-green-500"];
  const labels = ["", "弱", "中", "强"];
  if (!pwd) return null;
  return (
    <div className="flex items-center gap-2 mt-1.5">
      <div className="flex gap-1 flex-1">
        {[0, 1, 2].map((i) => (
          <div key={i} className={`h-1 flex-1 rounded-full transition-all ${i < score ? colors[score] : "bg-muted"}`} />
        ))}
      </div>
      <span className="text-[11px] text-muted-foreground">{labels[score]}</span>
    </div>
  );
}

export default function RegisterPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();

  const [form, setForm] = useState({
    username: "", nickname: "", password: "", confirm: "", grade: "",
  });
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function update(field: keyof typeof form, val: string) {
    setForm((f) => ({ ...f, [field]: val }));
  }

  const passwordMatch = form.password === form.confirm;
  const canSubmit =
    form.username.trim().length >= 3 &&
    form.password.length >= 6 &&
    passwordMatch &&
    !loading;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError("");
    try {
      await register({
        username: form.username.trim(),
        nickname: form.nickname.trim() || form.username.trim(),
        password: form.password,
        grade: form.grade || undefined,
      });
      // Auto-login after register
      const loginData = await login({ username: form.username.trim(), password: form.password });
      const token = loginData.access_token ?? loginData.token;
      const user = loginData.user ?? {
        id: "", username: form.username.trim(), nickname: form.nickname.trim() || form.username.trim(),
      };
      setAuth(user, token);
      router.replace("/dashboard");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "注册失败，请稍后重试";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo */}
        <div className="text-center space-y-2">
          <div className="w-14 h-14 rounded-2xl bg-primary/8 flex items-center justify-center mx-auto shadow-sm ring-1 ring-primary/15">
            <SpiralLogo className="w-8 h-8 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">创建账号</h1>
            <p className="text-sm text-muted-foreground mt-0.5">开始你的 AI 学习之旅</p>
          </div>
        </div>

        <Card>
          <CardContent className="py-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Username */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground" htmlFor="username">
                  用户名 <span className="text-destructive">*</span>
                </label>
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  value={form.username}
                  onChange={(e) => update("username", e.target.value)}
                  placeholder="至少3位，仅字母/数字/下划线"
                  className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>

              {/* Nickname */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground" htmlFor="nickname">
                  昵称
                </label>
                <input
                  id="nickname"
                  type="text"
                  value={form.nickname}
                  onChange={(e) => update("nickname", e.target.value)}
                  placeholder="留空则使用用户名"
                  className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>

              {/* Grade */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">年级</label>
                <div className="flex flex-wrap gap-1.5">
                  {GRADES.map((g) => (
                    <button
                      key={g}
                      type="button"
                      onClick={() => update("grade", form.grade === g ? "" : g)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                        form.grade === g
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-background text-muted-foreground border-border hover:border-primary/50"
                      }`}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground" htmlFor="password">
                  密码 <span className="text-destructive">*</span>
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPwd ? "text" : "password"}
                    autoComplete="new-password"
                    value={form.password}
                    onChange={(e) => update("password", e.target.value)}
                    placeholder="至少6位"
                    className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 pr-10 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd((s) => !s)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                <PasswordStrength pwd={form.password} />
              </div>

              {/* Confirm */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground" htmlFor="confirm">
                  确认密码 <span className="text-destructive">*</span>
                </label>
                <div className="relative">
                  <input
                    id="confirm"
                    type={showPwd ? "text" : "password"}
                    autoComplete="new-password"
                    value={form.confirm}
                    onChange={(e) => update("confirm", e.target.value)}
                    placeholder="再次输入密码"
                    className={`w-full rounded-lg border bg-background px-3.5 py-2.5 pr-10 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 ${
                      form.confirm && !passwordMatch
                        ? "border-destructive focus:ring-destructive/40"
                        : form.confirm && passwordMatch
                        ? "border-green-500 focus:ring-green-500/40"
                        : "border-border focus:ring-primary/40"
                    }`}
                  />
                  {form.confirm && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      {passwordMatch ? (
                        <CheckCircle2 size={15} className="text-green-500" />
                      ) : (
                        <AlertCircle size={15} className="text-destructive" />
                      )}
                    </div>
                  )}
                </div>
                {form.confirm && !passwordMatch && (
                  <p className="text-xs text-destructive">两次密码不一致</p>
                )}
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
                disabled={!canSubmit}
                size="lg"
                className="w-full gap-2 mt-1"
              >
                {loading && <Loader2 size={15} className="animate-spin" />}
                {loading ? "注册中…" : "注册并开始学习"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-sm text-muted-foreground">
          已有账号？{" "}
          <Link href="/login" className="text-primary hover:underline font-medium">
            直接登录
          </Link>
        </p>
      </div>
    </div>
  );
}
