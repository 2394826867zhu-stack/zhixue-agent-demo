"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Sparkles, BookOpen, Clock, ChevronRight,
  FileText, Loader2, CheckCircle2
} from "lucide-react";
import { listNotes, generateNote } from "@/lib/api";

const SUBJECTS = ["数学", "物理", "化学", "生物", "语文", "英语", "历史", "地理", "政治"];

interface Note {
  id: string;
  title: string;
  subject: string;
  summary?: string;
  kp_count?: number;
  created_at: string;
}

const SUBJECT_COLORS: Record<string, string> = {
  数学: "bg-blue-100 text-blue-700",
  物理: "bg-purple-100 text-purple-700",
  化学: "bg-green-100 text-green-700",
  生物: "bg-teal-100 text-teal-700",
  语文: "bg-red-100 text-red-700",
  英语: "bg-amber-100 text-amber-700",
  历史: "bg-orange-100 text-orange-700",
  地理: "bg-cyan-100 text-cyan-700",
  政治: "bg-pink-100 text-pink-700",
};

// Fallback mock data
const MOCK_NOTES: Note[] = [
  { id: "1", title: "等差数列与等比数列", subject: "数学", summary: "等差数列公差恒定，等比数列公比恒定。求和公式推导及应用场景对比分析。", kp_count: 8, created_at: "2026-05-16" },
  { id: "2", title: "牛顿三大运动定律",   subject: "物理", summary: "惯性定律、加速度定律、作用反作用定律的条件与适用范围，力学分析方法总结。", kp_count: 12, created_at: "2026-05-15" },
  { id: "3", title: "氧化还原反应基础",   subject: "化学", summary: "化合价变化判断氧化还原，氧化剂还原剂的判断，电子转移守恒配平法。", kp_count: 6, created_at: "2026-05-14" },
  { id: "4", title: "细胞的能量供应与利用", subject: "生物", summary: "ATP的合成与水解，细胞呼吸与光合作用的关系，能量代谢调节机制。", kp_count: 10, created_at: "2026-05-13" },
];

function GenerateTab({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient();
  const [topic, setTopic] = useState("");
  const [subject, setSubject] = useState(SUBJECTS[0]);

  const generateMutation = useMutation({
    mutationFn: () => generateNote({ topic, subject }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      setTopic("");
      onSuccess();
    },
  });

  return (
    <div className="space-y-5 max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles size={16} className="text-primary" /> AI 生成笔记
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Subject */}
          <div>
            <label className="text-sm font-medium text-foreground mb-2 block">学科</label>
            <div className="flex flex-wrap gap-2">
              {SUBJECTS.map((s) => (
                <button
                  key={s}
                  onClick={() => setSubject(s)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                    subject === s
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background text-muted-foreground border-border hover:border-primary/50"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Topic */}
          <div>
            <label className="text-sm font-medium text-foreground mb-2 block">主题或内容</label>
            <textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="输入你想学习的知识点、章节名称，或直接粘贴课本原文…"
              className="w-full min-h-[120px] rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none"
            />
          </div>

          <Button
            onClick={() => generateMutation.mutate()}
            disabled={!topic.trim() || generateMutation.isPending}
            size="lg"
            className="w-full gap-2"
          >
            {generateMutation.isPending ? (
              <><Loader2 size={16} className="animate-spin" /> AI 生成中…</>
            ) : (
              <><Sparkles size={16} /> 生成笔记</>
            )}
          </Button>

          {generateMutation.isSuccess && (
            <div className="flex items-center gap-2.5 p-3.5 rounded-lg bg-green-50 border border-green-200 text-green-700 text-sm">
              <CheckCircle2 size={16} />
              笔记已生成！知识点和闪卡已同步创建。
            </div>
          )}

          {generateMutation.isError && (
            <div className="flex items-center gap-2.5 p-3.5 rounded-lg bg-destructive/5 border border-destructive/20 text-destructive text-sm">
              生成失败，请检查网络后重试
            </div>
          )}
        </CardContent>
      </Card>

      <div className="p-4 rounded-xl border border-dashed border-border bg-muted/30 space-y-2">
        <p className="text-xs font-medium text-foreground">💡 生成效果更好的技巧</p>
        <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
          <li>可以直接粘贴课本段落，AI 会提炼重点</li>
          <li>具体的主题比宽泛的主题效果更好</li>
          <li>生成后可在"我的笔记"查看并继续补充</li>
        </ul>
      </div>
    </div>
  );
}

function NotesList() {
  const [filterSubject, setFilterSubject] = useState<string | null>(null);

  const { data: apiNotes, isLoading, isError } = useQuery<Note[]>({
    queryKey: ["notes"],
    queryFn: () => listNotes(1),
  });

  const allNotes: Note[] = isError || (!isLoading && !apiNotes)
    ? MOCK_NOTES
    : (apiNotes ?? []);

  const filtered = filterSubject
    ? allNotes.filter((n) => n.subject === filterSubject)
    : allNotes;

  const subjects = [...new Set(allNotes.map((n) => n.subject))];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-primary" size={28} />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Filter */}
      <div className="flex flex-wrap gap-2 items-center">
        <button
          onClick={() => setFilterSubject(null)}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
            !filterSubject ? "bg-primary text-primary-foreground border-primary" : "bg-background text-muted-foreground border-border hover:border-primary/50"
          }`}
        >
          全部
        </button>
        {subjects.map((s) => (
          <button
            key={s}
            onClick={() => setFilterSubject(filterSubject === s ? null : s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              filterSubject === s ? "bg-primary text-primary-foreground border-primary" : "bg-background text-muted-foreground border-border hover:border-primary/50"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Notes grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.map((note) => (
          <Card
            key={note.id}
            size="sm"
            className="cursor-pointer hover:ring-primary/30 hover:shadow-md transition-all group"
          >
            <CardContent className="py-4 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SUBJECT_COLORS[note.subject] || "bg-muted text-muted-foreground"}`}>
                  {note.subject}
                </span>
                <ChevronRight size={14} className="text-muted-foreground group-hover:text-primary transition-colors shrink-0 mt-0.5" />
              </div>
              <div>
                <h3 className="font-semibold text-sm text-foreground leading-snug">{note.title}</h3>
                {note.summary && (
                  <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed line-clamp-2">{note.summary}</p>
                )}
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground pt-1 border-t border-border">
                {note.kp_count != null && (
                  <span className="flex items-center gap-1"><FileText size={11} /> {note.kp_count} 个知识点</span>
                )}
                <span className="flex items-center gap-1"><Clock size={11} /> {note.created_at?.slice(0, 10)}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <BookOpen size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">没有匹配的笔记</p>
        </div>
      )}
    </div>
  );
}

export default function NotesPage() {
  const [tab, setTab] = useState<"generate" | "list">("list");

  const { data: apiNotes } = useQuery<Note[]>({
    queryKey: ["notes"],
    queryFn: () => listNotes(1),
  });

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto space-y-5 md:space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">笔记</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            共 {apiNotes?.length ?? "—"} 篇笔记
          </p>
        </div>
        <Button onClick={() => setTab("generate")} className="gap-2">
          <Sparkles size={15} /> 生成笔记
        </Button>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit">
        {[
          { key: "list", label: "我的笔记", icon: BookOpen },
          { key: "generate", label: "AI 生成", icon: Sparkles },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key as "generate" | "list")}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              tab === key
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {tab === "list"
        ? <NotesList />
        : <GenerateTab onSuccess={() => setTab("list")} />
      }
    </div>
  );
}
