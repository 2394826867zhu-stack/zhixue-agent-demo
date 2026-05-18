import axios from "axios";
import curriculumSeed from "@/lib/curriculum-seed.json";

const DEFAULT_API_BASE = "http://localhost:8000/v1";
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE).trim().replace(/\/+$/, "");

type DemoTask = {
  id: string;
  title: string;
  task_type: string;
  subject?: string;
  estimated_minutes?: number;
  priority?: string;
  is_done: boolean;
  ai_priority_reason?: string;
};

type DemoNote = {
  id: string;
  title: string;
  subject: string;
  summary?: string;
  kp_count?: number;
  created_at: string;
};

type DemoFlashcard = {
  id: string;
  front: string;
  back: string;
  subject?: string;
  due_in?: string;
};

export type PathNode = {
  id: string;
  stage_id: string;
  title: string;
  node_type: "lesson" | "review" | "training" | "project";
  status: "locked" | "current" | "done" | "review";
  subject: string | null;
  estimated_minutes: number;
  reward: string | null;
  note_id: string | null;
  kp_ids: string[];
  prerequisite_ids: string[];
  sort_order: number;
  completed_at: string | null;
};

export type PathStage = {
  id: string;
  title: string;
  description: string;
  sort_order: number;
  progress: number;
  is_ai_generated: boolean;
  nodes: PathNode[];
};

export type CoachTip = {
  message: string;
  suggested_node_id: string | null;
  suggested_action: "start" | "review" | "continue" | null;
};

export type ProfileInsights = {
  total_notes: number;
  total_kps: number;
  mastered_kps: number;
  total_focus_minutes: number;
  total_pomodoros: number;
  total_flashcard_reviews: number;
  total_training_sessions: number;
  training_avg_score: number | null;
  total_guidance_sessions: number;
  streak_days: number;
  achievements_earned: number;
  achievements_total: number;
};

export type Achievement = {
  id: string;
  title: string;
  icon: string;
  description: string;
  earned: boolean;
  progress: number;
  target: number;
  progress_pct: number;
};

export type Reflection = {
  id: string;
  week_start: string;
  week_end: string;
  content: string;
  created_at: string;
  updated_at: string;
};

export type OnboardingDraft = {
  grade?: string;
  grade_type?: string;
  subjects?: string[];
  progress?: Record<string, string>;
  performance?: Record<string, string>;
  next_exam_name?: string;
  next_exam_date?: string;
  next_exam_subject?: string;
  goal?: string;
  upload?: string;
  [key: string]: unknown;
};

export type OnboardingStatus = {
  current_step: string;
  step_index: number;
  total_steps: number;
  completed: boolean;
  question: string;
  profile_draft: OnboardingDraft;
};

export type OnboardingChatResponse = {
  reply: string;
  step: string;
  step_index: number;
  total_steps: number;
  completed: boolean;
  profile_draft: OnboardingDraft;
};

export type CheckInUpdate = {
  kp_updates?: { kp_id: string; new_mastery: string; reason: string }[];
  kps_created?: { name: string; subject: string; mastery_status: string }[];
  tasks_created?: { title: string; subject: string; estimated_minutes: number }[];
};

export type CheckIn = {
  id: string;
  raw_content: string;
  ai_summary: string | null;
  parsed_updates: CheckInUpdate;
  created_at: string;
};

export type AgentChatEvent =
  | { thinking: string }
  | { delta: string }
  | { done: true; session_id: string; tools_called?: string[] }
  | { error: { code: string; message: string; recoverable: boolean } };

export type AgentChatHandlers = {
  onThinking?: (thinking: string) => void;
  onDelta?: (delta: string) => void;
  onDone?: (event: Extract<AgentChatEvent, { done: true }>) => void;
  onError?: (error: { code: string; message: string; recoverable: boolean }) => void;
};

export type UploadNoteFileResponse = {
  note_id: string;
  status: "pending" | "processing" | "done" | "failed";
};

export type GeneratedNoteResponse = {
  note_id: string;
  status: string;
  message?: string;
};

type CurriculumSeedLesson = {
  subject: string;
  grade_type: string;
  grade_year: number;
  semester: number;
  chapter_index: number;
  chapter_title: string;
  lesson_index: number;
  lesson_title: string;
  textbook_version: string;
  is_key: boolean;
};

const isBrowser = () => typeof window !== "undefined";

const isLocalHost = (hostname: string) =>
  ["localhost", "127.0.0.1", "::1"].includes(hostname);

const apiBaseIsLocal = () =>
  API_BASE.includes("localhost") || API_BASE.includes("127.0.0.1");

const getLocalStorageItem = (key: string) => {
  if (!isBrowser()) return null;
  try {
    return window.localStorage?.getItem(key);
  } catch {
    return null;
  }
};

export function isDemoMode() {
  if (process.env.NEXT_PUBLIC_DEMO_MODE === "true") return true;
  if (!isBrowser()) return false;

  const demoToken = getLocalStorageItem("access_token");
  const hasRealToken = !!demoToken && demoToken !== "dev-token" && demoToken !== "demo-token";
  if (hasRealToken) return false;

  const localOverride = getLocalStorageItem("zhiyao_demo_mode") === "true";
  const persistedAuth = getLocalStorageItem("zhiyao-auth") ?? "";
  const demoAuthSnapshot =
    persistedAuth.includes("dev-001") ||
    persistedAuth.includes("demo-user") ||
    persistedAuth.includes('"username":"demo"') ||
    persistedAuth.includes('"nickname":"Demo用户"');
  const externalViewerUsingLocalApi = apiBaseIsLocal() && !isLocalHost(window.location.hostname);

  return localOverride || demoToken === "dev-token" || demoToken === "demo-token" || demoAuthSnapshot || externalViewerUsingLocalApi;
}

function delay<T>(data: T, ms = 220): Promise<T> {
  return new Promise((resolve) => globalThis.setTimeout(() => resolve(data), ms));
}

function todayISO(offsetDays = 0) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

let demoTasks: DemoTask[] = [
  {
    id: "task-1",
    title: "复习数学闪卡（12张）",
    task_type: "flashcard_review",
    subject: "数学",
    estimated_minutes: 24,
    priority: "high",
    is_done: false,
    ai_priority_reason: "12张到期卡已等待复习，间隔重复效果最佳，控制在25分钟内完成。",
  },
  {
    id: "task-2",
    title: "错题重练：物理受力分析（3题）",
    task_type: "mistake_review",
    subject: "物理",
    estimated_minutes: 18,
    priority: "high",
    is_done: false,
    ai_priority_reason: "受力分析是本周错误率最高的考点，3道重练题可精准校准掌握度。",
  },
  {
    id: "task-3",
    title: "整理英语阅读高频词",
    task_type: "manual",
    subject: "英语",
    estimated_minutes: 16,
    priority: "normal",
    is_done: true,
    ai_priority_reason: "已识别出8个可沉淀为闪卡的高频词，整理后直接生成复习队列。",
  },
  {
    id: "task-4",
    title: "预习化学氧化还原反应",
    task_type: "manual",
    subject: "化学",
    estimated_minutes: 25,
    priority: "normal",
    is_done: false,
    ai_priority_reason: "化学知识点积累偏少，今天预习可为后续闪卡和训练打好基础。",
  },
];

let demoNotes: DemoNote[] = [
  {
    id: "note-1",
    title: "等差数列与等比数列",
    subject: "数学",
    summary: "等差数列公差恒定，等比数列公比恒定。重点对比求和公式、通项公式和常见题型。",
    kp_count: 8,
    created_at: todayISO(-1),
  },
  {
    id: "note-2",
    title: "牛顿三大运动定律",
    subject: "物理",
    summary: "惯性定律、加速度定律、作用反作用定律的适用条件，以及受力分析的基础步骤。",
    kp_count: 12,
    created_at: todayISO(-2),
  },
  {
    id: "note-3",
    title: "氧化还原反应基础",
    subject: "化学",
    summary: "通过化合价变化判断氧化还原，区分氧化剂和还原剂，并使用电子守恒进行配平。",
    kp_count: 6,
    created_at: todayISO(-3),
  },
  {
    id: "note-4",
    title: "细胞的能量供应与利用",
    subject: "生物",
    summary: "ATP 的合成与水解、细胞呼吸和光合作用之间的能量流转关系。",
    kp_count: 10,
    created_at: todayISO(-4),
  },
];

const demoCards: DemoFlashcard[] = [
  {
    id: "card-1",
    subject: "数学",
    front: "等差数列求和公式",
    back: "S_n = n(a_1 + a_n) / 2 = na_1 + n(n-1)d / 2，其中 d 为公差。",
    due_in: "今天",
  },
  {
    id: "card-2",
    subject: "物理",
    front: "牛顿第二定律",
    back: "物体的加速度与所受合外力成正比，与质量成反比，方向与合外力方向相同。",
    due_in: "今天",
  },
  {
    id: "card-3",
    subject: "化学",
    front: "氧化剂和还原剂如何判断？",
    back: "化合价降低的物质是氧化剂，化合价升高的物质是还原剂。",
    due_in: "今天",
  },
  {
    id: "card-4",
    subject: "英语",
    front: "elaborate",
    back: "动词：详细说明；形容词：精心制作的、复杂的。",
    due_in: "明天",
  },
];

let demoPathStages: PathStage[] = [
  {
    id: "stage-1",
    title: "阶段 1：建立基础框架",
    description: "先把核心概念和公式整理清楚，形成可复习的知识原子。",
    sort_order: 1,
    progress: 1,
    is_ai_generated: true,
    nodes: [
      {
        id: "node-1",
        stage_id: "stage-1",
        title: "整理等差与等比数列公式",
        node_type: "lesson",
        status: "done",
        subject: "数学",
        estimated_minutes: 18,
        reward: "公式徽章",
        note_id: "note-1",
        kp_ids: ["kp-1"],
        prerequisite_ids: [],
        sort_order: 1,
        completed_at: todayISO(-2),
      },
      {
        id: "node-2",
        stage_id: "stage-1",
        title: "复习牛顿三大运动定律",
        node_type: "review",
        status: "done",
        subject: "物理",
        estimated_minutes: 20,
        reward: "力学入门",
        note_id: "note-2",
        kp_ids: ["kp-2"],
        prerequisite_ids: [],
        sort_order: 2,
        completed_at: todayISO(-1),
      },
    ],
  },
  {
    id: "stage-2",
    title: "阶段 2：进入主动提取",
    description: "用闪卡、错题和小训练把知识从“看懂”推进到“能用”。",
    sort_order: 2,
    progress: 0.55,
    is_ai_generated: true,
    nodes: [
      {
        id: "node-3",
        stage_id: "stage-2",
        title: "完成 12 张数学闪卡复习",
        node_type: "review",
        status: "current",
        subject: "数学",
        estimated_minutes: 24,
        reward: "连续复习 +1",
        note_id: null,
        kp_ids: ["kp-1"],
        prerequisite_ids: ["node-1"],
        sort_order: 1,
        completed_at: null,
      },
      {
        id: "node-4",
        stage_id: "stage-2",
        title: "物理受力分析错题重练",
        node_type: "training",
        status: "review",
        subject: "物理",
        estimated_minutes: 18,
        reward: "薄弱点修复",
        note_id: null,
        kp_ids: ["kp-2"],
        prerequisite_ids: ["node-2"],
        sort_order: 2,
        completed_at: null,
      },
      {
        id: "node-5",
        stage_id: "stage-2",
        title: "氧化还原反应判断训练",
        node_type: "training",
        status: "locked",
        subject: "化学",
        estimated_minutes: 25,
        reward: "化学基础",
        note_id: "note-3",
        kp_ids: ["kp-3"],
        prerequisite_ids: ["node-3"],
        sort_order: 3,
        completed_at: null,
      },
    ],
  },
  {
    id: "stage-3",
    title: "阶段 3：考前综合输出",
    description: "进入混合训练和费曼输出，检查能否跨知识点迁移。",
    sort_order: 3,
    progress: 0.12,
    is_ai_generated: true,
    nodes: [
      {
        id: "node-6",
        stage_id: "stage-3",
        title: "完成一次数学综合训练",
        node_type: "project",
        status: "locked",
        subject: "数学",
        estimated_minutes: 35,
        reward: "阶段通关",
        note_id: null,
        kp_ids: ["kp-1"],
        prerequisite_ids: ["node-5"],
        sort_order: 1,
        completed_at: null,
      },
    ],
  },
];

let demoReflections: Reflection[] = [
  {
    id: "reflection-1",
    week_start: todayISO(-6),
    week_end: todayISO(),
    content: "这周数学复习节奏比较稳定，物理受力分析还需要更多主动训练。下周优先把错题重练和闪卡复习固定下来。",
    created_at: todayISO(),
    updated_at: todayISO(),
  },
];

const onboardingSteps = [
  {
    key: "grade",
    question: "先告诉我你现在是几年级？",
    suggestions: ["初一", "初二", "初三", "高一", "高二", "高三"],
  },
  {
    key: "subjects",
    question: "这学期你最想让我重点照看的科目有哪些？",
    suggestions: ["数学、物理、英语", "语文、数学、英语", "全科都要", "先管薄弱科"],
  },
  {
    key: "progress",
    question: "你们最近各科大概学到哪里了？可以像“数学二次函数，物理浮力”这样说。",
    suggestions: ["数学二次函数，物理浮力", "英语 Unit 4，化学酸碱盐", "我不确定，之后上传课程表"],
  },
  {
    key: "performance",
    question: "目前成绩大概处于什么水平？不用精确，我只需要判断节奏。",
    suggestions: ["班级前 20%", "中等偏上", "中等", "有点吃力"],
  },
  {
    key: "next_exam",
    question: "下一次重要考试是什么？大概几月几号？",
    suggestions: ["期末考试，6月25日", "一模，6月12日", "月考，下周五", "暂时不清楚"],
  },
  {
    key: "goal",
    question: "这段时间你最希望我帮你达成什么目标？",
    suggestions: ["稳定完成作业和复习", "把数学提上去", "冲刺重点高中", "减少学习焦虑"],
  },
  {
    key: "upload",
    question: "如果你愿意，可以把课程表、成绩单或考试安排的文字粘贴给我；也可以先跳过。",
    suggestions: ["先跳过", "我有课程表", "我有成绩单", "我有考试安排"],
  },
  {
    key: "confirm",
    question: "我已经整理好你的学习档案。确认后，我会建立基础知识库、考试时间线和第一周计划。",
    suggestions: ["确认建立", "我想修改前面信息"],
  },
];

let demoOnboardingIndex = 0;
let demoOnboardingCompleted = false;
let demoOnboardingDraft: OnboardingDraft = {};
let demoCheckIns: CheckIn[] = [];

const buildDemoOnboardingStatus = (): OnboardingStatus => {
  const step = onboardingSteps[Math.min(demoOnboardingIndex, onboardingSteps.length - 1)];
  return {
    current_step: demoOnboardingCompleted ? "completed" : step.key,
    step_index: demoOnboardingCompleted ? onboardingSteps.length : demoOnboardingIndex,
    total_steps: onboardingSteps.length,
    completed: demoOnboardingCompleted,
    question: demoOnboardingCompleted ? "学习档案已经建立，可以开始每日同步了。" : step.question,
    profile_draft: demoOnboardingDraft,
  };
};

const applyDemoOnboardingAnswer = (message: string) => {
  const step = onboardingSteps[Math.min(demoOnboardingIndex, onboardingSteps.length - 1)];
  if (step.key === "grade") demoOnboardingDraft.grade = message;
  if (step.key === "subjects") demoOnboardingDraft.subjects = message.split(/[、,，\s]+/).filter(Boolean);
  if (step.key === "progress") demoOnboardingDraft.progress = { 最近学习: message };
  if (step.key === "performance") demoOnboardingDraft.performance = { 当前水平: message };
  if (step.key === "next_exam") {
    demoOnboardingDraft.next_exam_name = message;
    demoOnboardingDraft.next_exam_date = "2026-06-25";
  }
  if (step.key === "goal") demoOnboardingDraft.goal = message;
  if (step.key === "upload") demoOnboardingDraft.upload = message;
  if (step.key === "confirm") {
    demoOnboardingCompleted = true;
    try {
      localStorage.setItem("zhiyao_onboarding_completed", "true");
      localStorage.removeItem("zhiyao_needs_onboarding");
    } catch {}
  } else {
    demoOnboardingIndex = Math.min(demoOnboardingIndex + 1, onboardingSteps.length - 1);
  }
};

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = isBrowser() ? localStorage.getItem("access_token") : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401 && isBrowser() && !isDemoMode()) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// ---- Progress ----
export const getOverview = () => {
  if (isDemoMode()) {
    return delay({
      total_kps: 142,
      due_cards: demoCards.length,
      weekly_minutes: 486,
      mistake_count: 7,
      weekly_pomodoros: 19,
      kp_delta_week: 12,
    });
  }
  return api.get("/progress/overview").then((r) => r.data.data);
};

export const getHeatmap = (days = 90) => {
  if (isDemoMode()) {
    const heatmap = Array.from({ length: days }, (_, index) => {
      const offset = index - days + 1;
      const pattern = (index * 17 + 11) % 100;
      const minutes = pattern < 18 ? 0 : pattern < 45 ? 18 + (pattern % 24) : 42 + (pattern % 58);
      return { date: todayISO(offset), minutes };
    });
    return delay(heatmap);
  }
  return api.get(`/progress/heatmap?days=${days}`).then((r) => r.data.data);
};

export const getSubjects = () => {
  if (isDemoMode()) {
    return delay([
      { subject: "数学", mastery: 0.78, kp_count: 44, weekly_minutes: 132 },
      { subject: "物理", mastery: 0.62, kp_count: 31, weekly_minutes: 116 },
      { subject: "英语", mastery: 0.72, kp_count: 27, weekly_minutes: 86 },
      { subject: "化学", mastery: 0.58, kp_count: 18, weekly_minutes: 74 },
    ]);
  }
  return api.get("/progress/subjects").then((r) => r.data.data);
};

export const getWeeklyReport = (offset = 0) => {
  if (isDemoMode()) {
    return delay({
      new_kps: 12,
      flashcard_completion_rate: 0.86,
      training_avg_score: 84,
      total_minutes: 486,
      weak_subjects: offset === 0 ? ["物理", "化学"] : [],
      ai_advice:
        offset === 0
          ? "本周节奏稳定，数学和英语复习完成率较高。建议明天优先处理物理受力分析错题，再用 20 分钟整理化学氧化还原的判断规则。"
          : "历史周报已归档，可继续查看当前周建议。",
    });
  }
  return api.get(`/progress/weekly-report?offset_weeks=${offset}`).then((r) => r.data.data);
};

// ---- Tasks ----
export const getTodayTasks = () => {
  if (isDemoMode()) return delay(demoTasks);
  return api.get("/tasks").then((r) => r.data.data);
};

export const generateTasks = () => {
  if (isDemoMode()) {
    demoTasks = [
      ...demoTasks,
      {
        id: `task-${Date.now()}`,
        title: "AI 建议：用 15 分钟复盘今日最薄弱概念",
        task_type: "manual",
        subject: "综合",
        estimated_minutes: 15,
        priority: "normal",
        is_done: false,
      },
    ];
    return delay(demoTasks);
  }
  return api.post("/tasks/generate").then((r) => r.data.data);
};

export const updateTask = (id: string, body: object) => {
  if (isDemoMode()) {
    const nextBody = body as { status?: string; is_done?: boolean };
    demoTasks = demoTasks.map((task) =>
      task.id === id
        ? { ...task, ...body, is_done: nextBody.is_done ?? (nextBody.status ? nextBody.status === "done" : task.is_done) }
        : task
    );
    return delay(demoTasks.find((task) => task.id === id) ?? { id, ...body });
  }
  return api.patch(`/tasks/${id}`, body).then((r) => r.data.data);
};

export const getPomodoroStats = () => {
  if (isDemoMode()) return delay({ sessions: 19, focus_minutes: 486, streak_days: 6 });
  return api.get("/tasks/pomodoro/stats").then((r) => r.data.data);
};

export const createTask = (body: object) => {
  if (isDemoMode()) {
    const t = { id: `task-${Date.now()}`, title: "新任务", task_type: "manual", is_done: false, priority: "normal", estimated_minutes: 25, ...body };
    demoTasks = [t as typeof demoTasks[0], ...demoTasks];
    return delay(t);
  }
  return api.post("/tasks", body).then((r) => r.data.data);
};

export const deleteTask = (id: string) => {
  if (isDemoMode()) { demoTasks = demoTasks.filter((t) => t.id !== id); return delay({ success: true }); }
  return api.delete(`/tasks/${id}`).then((r) => r.data.data);
};

export const aiSortTasks = () => {
  if (isDemoMode()) return delay(demoTasks);
  return api.post("/tasks/ai-sort").then((r) => r.data.data);
};

export const recordPomodoro = (body: { task_id?: string; duration_minutes: number; started_at: string; completed_at: string; note?: string }) => {
  if (isDemoMode()) return delay({ id: `pomo-${Date.now()}`, duration_minutes: body.duration_minutes });
  return api.post("/tasks/pomodoro", body).then((r) => r.data.data);
};

export const getWeeklyProgress = () => {
  if (isDemoMode()) {
    const days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
    return delay(days.map((day, i) => ({ day, minutes: [45, 30, 60, 25, 75, 90, 50][i], cards: [12, 8, 18, 6, 22, 28, 14][i] })));
  }
  return api.get("/progress/weekly-report").then((r) => r.data.data);
};

// ---- Notes ----
export const listNotes = (page = 1) => {
  if (isDemoMode()) return delay(page === 1 ? demoNotes : []);
  return api.get(`/notes?page=${page}`).then((r) => r.data.data.items ?? r.data.data);
};

export const generateNote = (body: { topic?: string; subject?: string; [key: string]: unknown }) => {
  if (isDemoMode()) {
    const topic = body.topic?.trim() || "AI 整理学习笔记";
    const note = {
      id: crypto.randomUUID(),
      title: topic.length > 24 ? `${topic.slice(0, 24)}...` : topic,
      subject: body.subject || "综合",
      summary: "已根据输入内容提炼出核心概念、易错点和下一步复习建议，可继续生成闪卡和任务。",
      kp_count: 5,
      created_at: todayISO(),
    };
    demoNotes = [note, ...demoNotes];
    return delay(note, 600);
  }
  return api.post("/notes/generate", body).then((r) => r.data.data);
};

export const generateNoteWithAgent = (body: { topic: string; subject?: string; content?: string }): Promise<GeneratedNoteResponse> => {
  if (isDemoMode()) {
    const source = body.content?.trim() || body.topic;
    const note = {
      id: crypto.randomUUID(),
      title: source.length > 24 ? `${source.slice(0, 24)}...` : source,
      subject: body.subject || "综合",
      summary: "Agent 已接收生成任务，正在整理精读版、应考速览和知识框架。",
      kp_count: 0,
      created_at: todayISO(),
    };
    demoNotes = [note, ...demoNotes];
    return delay({ note_id: note.id, status: "generating", message: "Agent 已开始生成笔记" }, 600);
  }
  return api.post("/agent/generate-note", body).then((r) => r.data.data).catch((err) => {
    const detail = err?.response?.data?.message || err?.response?.data?.detail || err?.message;
    throw new Error(detail || "Agent 笔记生成失败");
  });
};

export const uploadNoteText = (body: { title?: string; subject?: string; content: string }): Promise<UploadNoteFileResponse> => {
  if (isDemoMode()) {
    const note = {
      id: crypto.randomUUID(),
      title: body.title || body.content.slice(0, 24) || "粘贴内容生成笔记",
      subject: body.subject || "综合",
      summary: "文本资料已进入处理队列，稍后会自动整理为笔记、知识点与闪卡。",
      kp_count: 0,
      created_at: todayISO(),
    };
    demoNotes = [note, ...demoNotes];
    return delay({ note_id: note.id, status: "processing" }, 600);
  }
  return api.post("/notes/upload/text", body).then((r) => r.data.data);
};

export const uploadNoteFile = (file: File, subject?: string): Promise<UploadNoteFileResponse> => {
  if (isDemoMode()) {
    const note = {
      id: crypto.randomUUID(),
      title: file.name.replace(/\.[^.]+$/, "") || "上传资料生成笔记",
      subject: subject || "综合",
      summary: "资料已进入处理队列，稍后会自动整理为笔记、知识点与闪卡。",
      kp_count: 0,
      created_at: todayISO(),
    };
    demoNotes = [note, ...demoNotes];
    return delay({ note_id: note.id, status: "processing" }, 600);
  }

  const formData = new FormData();
  formData.append("file", file);
  if (subject) formData.append("subject", subject);

  return api
    .post("/notes/upload/file", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data.data);
};

export const getNote = (id: string) => {
  if (isDemoMode()) {
    const note = demoNotes.find((n) => n.id === id) ?? demoNotes[0];
    return delay({
      ...note,
      source_type: "ai_generated",
      status: note.id.includes("agent") || note.id.includes("text") || note.id.includes("file") ? "processing" : "done",
      full_version: `## ${note.title}\n\n${note.summary || "这是 Agent 生成的示例精读内容。"}\n\n- 核心概念\n- 关键公式\n- 典型例题`,
      exam_version: `## 应考速览\n\n围绕「${note.title}」优先掌握定义、公式和常见题型。`,
      graph_mermaid: "graph TD\nA[核心概念] --> B[公式]\nA --> C[例题]\nC --> D[复习任务]",
      difficulty_points: [],
      flashcards_generated: false,
      knowledge_points: [],
    });
  }
  return api.get(`/notes/${id}`).then((r) => r.data.data);
};

export const deleteNote = (id: string) => {
  if (isDemoMode()) { demoNotes = demoNotes.filter((n) => n.id !== id); return delay({ success: true }); }
  return api.delete(`/notes/${id}`).then((r) => r.data.data);
};

// ---- Flashcards ----
export const getDueCards = (page = 1) => {
  if (isDemoMode()) return delay(page === 1 ? demoCards : []);
  return api.get(`/flashcards/due?page=${page}`).then((r) => r.data.data.items ?? r.data.data);
};

export const reviewCard = (id: string, rating: number) => {
  if (isDemoMode()) return delay({ id, rating, next_review: rating >= 4 ? "3天后" : "明天" });
  return api.post(`/flashcards/${id}/review`, { rating }).then((r) => r.data.data);
};

// ---- Knowledge Points ----
export const listKPs = (params?: object) => {
  if (isDemoMode()) {
    return delay([
      { id: "kp-1", name: "等差数列求和", subject: "数学", mastery_status: "reviewing", stability: 3.2, next_review_date: null, bloom_level: "apply", flashcard_count: 2 },
      { id: "kp-2", name: "受力分析", subject: "物理", mastery_status: "learning", stability: null, next_review_date: null, bloom_level: "apply", flashcard_count: 1 },
      { id: "kp-3", name: "氧化还原判断", subject: "化学", mastery_status: "learning", stability: 1.1, next_review_date: null, bloom_level: "understand", flashcard_count: 1 },
      { id: "kp-4", name: "阅读主旨题", subject: "英语", mastery_status: "reviewing", stability: 4.5, next_review_date: null, bloom_level: "analyze", flashcard_count: 3 },
    ]);
  }
  return api.get("/knowledge-points", { params }).then((r) => r.data.data.items ?? r.data.data);
};

export const getKP = (id: string) => {
  if (isDemoMode()) {
    const demo = [
      { id: "kp-1", name: "等差数列求和", subject: "数学", mastery_status: "reviewing", bloom_level: "apply", flashcard_count: 2, content: "## 等差数列求和公式\n\n设等差数列首项为 $a_1$，公差为 $d$，共 $n$ 项，则：\n\n$$S_n = \\frac{n(a_1 + a_n)}{2} = na_1 + \\frac{n(n-1)}{2}d$$\n\n**适用条件**：数列必须是等差数列，即相邻项之差恒定。\n\n**例题**：求 1+2+3+…+100 = $\\frac{100×101}{2}$ = 5050", key_formula: "$$S_n = \\frac{n(a_1+a_n)}{2}$$", note_id: null },
      { id: "kp-2", name: "受力分析", subject: "物理", mastery_status: "learning", bloom_level: "apply", flashcard_count: 1, content: "## 受力分析方法\n\n1. **确定研究对象**：明确要分析哪个物体\n2. **找重力**：任何有质量的物体都受重力 $G=mg$\n3. **找支持力**：与接触面垂直\n4. **找摩擦力**：与接触面平行，阻碍相对运动\n5. **找其他力**：弹力、电磁力等", key_formula: "$G = mg$，$g ≈ 9.8 m/s^2$", note_id: null },
    ];
    return delay(demo.find((k) => k.id === id) ?? demo[0]);
  }
  return api.get(`/knowledge-points/${id}`).then((r) => r.data.data);
};

export const updateKP = (id: string, data: object) => {
  if (isDemoMode()) return delay({ id, ...data });
  return api.patch(`/knowledge-points/${id}`, data).then((r) => r.data.data);
};

export const deleteKP = (id: string) => {
  if (isDemoMode()) return delay({ success: true });
  return api.delete(`/knowledge-points/${id}`).then((r) => r.data.data);
};

export const createKP = (data: object) => {
  if (isDemoMode()) return delay({ id: `kp-${Date.now()}`, mastery_status: "new", bloom_level: "remember", flashcard_count: 0, ...data });
  return api.post("/knowledge-points", data).then((r) => r.data.data);
};

export const getKPStats = () => {
  if (isDemoMode()) return delay({ total: 4, new: 0, learning: 2, reviewing: 2, mastered: 0, by_subject: {} });
  return api.get("/knowledge-points/stats").then((r) => r.data.data);
};

// ---- Curriculum ----
const demoCurriculumKP = {
  id: "kp-1",
  name: "空间向量及其线性运算",
  subject: "数学",
  mastery_status: "learning",
  bloom_level: "apply",
  flashcard_count: 2,
  content: "## 空间向量\n\n空间向量用于描述三维空间中的方向和长度，线性运算包括加法、减法和数乘。它是立体几何坐标化的基础。",
  key_formula: "$$\\vec{a}+\\vec{b}=(x_1+x_2,y_1+y_2,z_1+z_2)$$",
  chapter_id: "cur-1",
};

const localCurriculum = curriculumSeed as CurriculumSeedLesson[];

function localLessonId(item: CurriculumSeedLesson) {
  return [
    item.grade_type,
    item.grade_year,
    item.semester,
    item.subject,
    item.chapter_index,
    item.lesson_index,
  ].join("-");
}

function findLocalLesson(id: string) {
  return localCurriculum.find((item) => localLessonId(item) === id);
}

function isUuidLike(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

function buildLocalCurriculum(params: { grade_type?: string; grade_year?: number; subject?: string; semester?: number } = {}) {
  const filtered = localCurriculum.filter((item) => {
    if (params.grade_type && item.grade_type !== params.grade_type) return false;
    if (params.grade_year && item.grade_year !== params.grade_year) return false;
    if (params.subject && item.subject !== params.subject) return false;
    if (params.semester && item.semester !== params.semester) return false;
    return true;
  });

  const groups = new Map<string, {
    chapter_index: number;
    chapter_title: string;
    subject: string;
    semester: number;
    lessons: Array<CurriculumSeedLesson & { id: string; kp_count: number; created_at: string }>;
  }>();

  for (const item of filtered) {
    const key = `${item.subject}-${item.semester}-${item.chapter_index}-${item.chapter_title}`;
    if (!groups.has(key)) {
      groups.set(key, {
        chapter_index: item.chapter_index,
        chapter_title: item.chapter_title,
        subject: item.subject,
        semester: item.semester,
        lessons: [],
      });
    }
    groups.get(key)!.lessons.push({
      ...item,
      id: localLessonId(item),
      kp_count: item.subject === "数学" && item.grade_year === 2 && item.chapter_index === 1 && item.lesson_index === 1 ? 1 : 0,
      created_at: todayISO(-7),
    });
  }

  return Array.from(groups.values()).sort((a, b) =>
    a.subject.localeCompare(b.subject, "zh-CN") ||
    a.semester - b.semester ||
    a.chapter_index - b.chapter_index
  );
}

export const getCurriculumChapters = (params: { grade_type?: string; grade_year?: number; subject?: string; semester?: number } = {}) => {
  if (isDemoMode()) return delay(buildLocalCurriculum(params));
  return api.get("/curriculum/chapters", { params }).then((r) => r.data.data).catch(() => buildLocalCurriculum(params));
};

export const getChapterKPs = (chapterId: string) => {
  if (isDemoMode()) return delay(chapterId.endsWith("数学-1-1") ? [demoCurriculumKP] : []);
  if (!isUuidLike(chapterId)) return delay(chapterId.endsWith("数学-1-1") ? [demoCurriculumKP] : []);
  return api.get(`/curriculum/chapters/${chapterId}/my-kps`).then((r) => r.data.data);
};

export const linkKPToChapter = (chapterId: string, kpId: string) => {
  if (isDemoMode()) return delay({ id: kpId, chapter_id: chapterId });
  return api.post(`/curriculum/chapters/${chapterId}/link-kp`, { kp_id: kpId }).then((r) => r.data.data);
};

export const generateNoteFromChapter = (chapterId: string) => {
  if (isDemoMode()) {
    const note = {
      id: crypto.randomUUID(),
      title: "课程课时生成笔记",
      subject: "数学",
      summary: "已根据课程目录创建生成任务，稍后可在笔记库查看。",
      kp_count: 0,
      created_at: todayISO(),
    };
    demoNotes = [note, ...demoNotes];
    return delay({ note_id: note.id, status: "processing", chapter_id: chapterId }, 600);
  }
  if (!isUuidLike(chapterId)) {
    const lesson = findLocalLesson(chapterId);
    const topic = lesson ? `${lesson.lesson_title}｜${lesson.chapter_title}` : "课程课时生成笔记";
    const content = lesson
      ? `请围绕${lesson.grade_year}年级${lesson.subject}《${lesson.chapter_title}》中的“${lesson.lesson_title}”整理学习笔记，输出适合学生复习的定义、公式、例题、易错点和知识框架。`
      : topic;
    return generateNoteWithAgent({ topic, subject: lesson?.subject || "综合", content });
  }
  return api.post(`/curriculum/chapters/${chapterId}/generate-note`).then((r) => r.data.data);
};

// ---- Training ----
export const startTraining = (body: object) => {
  if (isDemoMode()) {
    const subject = (body as { subject?: string }).subject ?? "物理";
    return delay({
      id: "demo-session-1",
      mode: "subject",
      subject,
      status: "active",
      question_count: 3,
      answered_count: 0,
      avg_score: null,
      created_at: new Date().toISOString(),
      completed_at: null,
      questions: [
        { id: "demo-q1", knowledge_point_id: "demo-kp1", bloom_level: "remember", question_type: "fill_blank", question: `${subject}：请简要说明你对该学科最基础概念的理解。`, reference: null, user_answer: null, ai_score: null, ai_feedback: null, is_wrong: false, answered_at: null },
        { id: "demo-q2", knowledge_point_id: "demo-kp1", bloom_level: "understand", question_type: "fill_blank", question: `${subject}：举一个你学过的例子，解释其中用到的原理。`, reference: null, user_answer: null, ai_score: null, ai_feedback: null, is_wrong: false, answered_at: null },
        { id: "demo-q3", knowledge_point_id: "demo-kp2", bloom_level: "apply", question_type: "essay", question: `${subject}：综合运用所学知识，分析一个实际问题。`, reference: null, user_answer: null, ai_score: null, ai_feedback: null, is_wrong: false, answered_at: null },
      ],
    });
  }
  return api.post("/training/start", body).then((r) => r.data.data);
};

export const submitAnswer = (sessionId: string, questionId: string, body: object) => {
  if (isDemoMode()) {
    const score = 72 + Math.floor(Math.random() * 28);
    return delay({
      question_id: questionId,
      ai_score: score,
      ai_feedback: "思路清晰，关键公式选择正确。建议补充单位和中间步骤，方便后续复盘。",
      is_wrong: score < 60,
      reference: "参考答案：（这是 Demo 模式，真实训练会由 AI 生成详细参考答案）",
      session_completed: questionId === "demo-q3",
      session_avg_score: null,
    });
  }
  return api.post(`/training/${sessionId}/answer/${questionId}`, body).then((r) => r.data.data);
};

// ---- Guidance ----
const demoGuidanceStartResponse = (question: string) =>
  delay({
    session_id: `demo-guid-${Date.now()}`,
    message: {
      id: `msg-${Date.now()}`,
      role: "assistant",
      content: `好，我们先不急着给答案。你刚才提到“${question.slice(0, 32)}”，我想先确认一件事：你现在最卡住的是概念本身、解题步骤，还是不知道什么时候使用它？`,
    },
  });

const demoGuidanceChatResponse = (sessionId: string, message: string) =>
  delay({
    session_id: sessionId,
    message: {
      id: `msg-${Date.now()}`,
      role: "assistant",
      content: `我明白了。你说到“${message.slice(0, 28)}”，这里可以拆成两步看：先找已知条件，再判断它和目标之间缺哪一环。你愿意先用自己的话说说，你觉得最关键的已知条件是哪一个吗？`,
    },
  });

const shouldUseGuidanceFallback = (err: unknown) => {
  void err;
  return isDemoMode();
};

export const startGuidance = (body: { question: string; subject?: string }) => {
  if (isDemoMode()) return demoGuidanceStartResponse(body.question);
  return api.post("/guidance/sessions", body).then((r) => r.data.data).catch((err) => {
    if (shouldUseGuidanceFallback(err)) return demoGuidanceStartResponse(body.question);
    throw err;
  });
};

export const chatGuidance = (sessionId: string, message: string) => {
  if (isDemoMode()) return demoGuidanceChatResponse(sessionId, message);
  return api.post(`/guidance/sessions/${sessionId}/chat`, { message }).then((r) => r.data.data).catch((err) => {
    if (shouldUseGuidanceFallback(err)) return demoGuidanceChatResponse(sessionId, message);
    throw err;
  });
};

export const listGuidanceSessions = (page = 1) => {
  if (isDemoMode()) return delay({ items: [], total: 0 });
  return api.get(`/guidance/sessions?page=${page}`).then((r) => r.data.data).catch((err) => {
    if (shouldUseGuidanceFallback(err)) return delay({ items: [], total: 0, page, page_size: 10 });
    throw err;
  });
};

// ---- Learning Path ----
export const getPathStages = () => {
  if (isDemoMode()) return delay(demoPathStages);
  return api.get("/path/stages").then((r) => r.data.data);
};

export const generatePath = (body: { subjects?: string[]; goal?: string }) => {
  if (isDemoMode()) return delay(demoPathStages, 700);
  return api.post("/path/ai-generate", body).then((r) => r.data.data);
};

export const completePathNode = (nodeId: string) => {
  if (isDemoMode()) {
    let completed: PathNode | null = null;
    demoPathStages = demoPathStages.map((stage) => ({
      ...stage,
      nodes: stage.nodes.map((node) => {
        if (node.id !== nodeId) return node;
        completed = { ...node, status: "done", completed_at: todayISO() };
        return completed;
      }),
    }));
    return delay(completed ?? { id: nodeId });
  }
  return api.post(`/path/nodes/${nodeId}/complete`).then((r) => r.data.data);
};

export const getCoachTip = () => {
  if (isDemoMode()) {
    return delay<CoachTip>({
      message: "今天适合先完成数学闪卡复习，再用 18 分钟处理物理受力分析错题。保持轻量推进就很好。",
      suggested_node_id: "node-3",
      suggested_action: "start",
    });
  }
  return api.get("/path/coach-tip").then((r) => r.data.data);
};

export const createPathStage = (body: { title: string; description?: string; sort_order?: number }) => {
  if (isDemoMode()) {
    const stage: PathStage = {
      id: `stage-${Date.now()}`,
      title: body.title,
      description: body.description ?? "手动创建的学习阶段",
      sort_order: body.sort_order ?? demoPathStages.length + 1,
      progress: 0,
      is_ai_generated: false,
      nodes: [],
    };
    demoPathStages = [...demoPathStages, stage];
    return delay(stage);
  }
  return api.post("/path/stages", body).then((r) => r.data.data);
};

export const createPathNode = (body: Partial<PathNode> & { stage_id: string; title: string }) => {
  if (isDemoMode()) {
    const node: PathNode = {
      id: `node-${Date.now()}`,
      stage_id: body.stage_id,
      title: body.title,
      node_type: body.node_type ?? "lesson",
      status: body.status ?? "locked",
      subject: body.subject ?? null,
      estimated_minutes: body.estimated_minutes ?? 20,
      reward: body.reward ?? null,
      note_id: body.note_id ?? null,
      kp_ids: body.kp_ids ?? [],
      prerequisite_ids: body.prerequisite_ids ?? [],
      sort_order: body.sort_order ?? 1,
      completed_at: null,
    };
    demoPathStages = demoPathStages.map((stage) =>
      stage.id === node.stage_id ? { ...stage, nodes: [...stage.nodes, node] } : stage
    );
    return delay(node);
  }
  return api.post("/path/nodes", body).then((r) => r.data.data);
};

// ---- Profile ----
export const getProfileInsights = () => {
  if (isDemoMode()) {
    return delay<ProfileInsights>({
      total_notes: demoNotes.length,
      total_kps: 142,
      mastered_kps: 68,
      total_focus_minutes: 4860,
      total_pomodoros: 82,
      total_flashcard_reviews: 236,
      total_training_sessions: 18,
      training_avg_score: 84,
      total_guidance_sessions: 11,
      streak_days: 14,
      achievements_earned: 9,
      achievements_total: 20,
    });
  }
  return api.get("/profile/insights").then((r) => r.data.data);
};

export const getAchievements = () => {
  if (isDemoMode()) {
    const items: Achievement[] = [
      { id: "first_note", title: "初记者", icon: "N", description: "创建第一篇笔记", earned: true, progress: 1, target: 1, progress_pct: 100 },
      { id: "kp_50", title: "知识积累者", icon: "K", description: "累计 50 个知识点", earned: true, progress: 142, target: 50, progress_pct: 100 },
      { id: "flash_200", title: "复习高手", icon: "F", description: "完成 200 次闪卡复习", earned: true, progress: 236, target: 200, progress_pct: 100 },
      { id: "focus_100", title: "专注冠军", icon: "P", description: "完成 100 个番茄钟", earned: false, progress: 82, target: 100, progress_pct: 82 },
      { id: "streak_30", title: "月度坚持", icon: "S", description: "连续学习 30 天", earned: false, progress: 14, target: 30, progress_pct: 47 },
      { id: "guidance_10", title: "深度思考者", icon: "G", description: "完成 10 次引导问答", earned: true, progress: 11, target: 10, progress_pct: 100 },
    ];
    return delay(items);
  }
  return api.get("/profile/achievements").then((r) => r.data.data);
};

export const saveReflection = (body: { content: string; week_start?: string }) => {
  if (isDemoMode()) {
    const reflection: Reflection = {
      id: `reflection-${Date.now()}`,
      week_start: body.week_start ?? todayISO(-6),
      week_end: todayISO(),
      content: body.content,
      created_at: todayISO(),
      updated_at: todayISO(),
    };
    demoReflections = [reflection, ...demoReflections.filter((item) => item.week_start !== reflection.week_start)];
    return delay(reflection);
  }
  return api.post("/profile/reflection", body).then((r) => r.data.data);
};

export const listReflections = (page = 1, page_size = 10) => {
  if (isDemoMode()) {
    return delay({ items: demoReflections, total: demoReflections.length, page, page_size });
  }
  return api.get(`/profile/reflection?page=${page}&page_size=${page_size}`).then((r) => r.data.data);
};

// ---- Onboarding ----
export const getOnboardingStatus = () => {
  if (isDemoMode()) return delay(buildDemoOnboardingStatus());
  return api.get("/onboarding/status").then((r) => r.data.data);
};

export const sendOnboardingMessage = (message: string) => {
  if (isDemoMode()) {
    applyDemoOnboardingAnswer(message);
    const status = buildDemoOnboardingStatus();
    return delay<OnboardingChatResponse>({
      reply: status.question,
      step: status.current_step,
      step_index: status.step_index,
      total_steps: status.total_steps,
      completed: status.completed,
      profile_draft: status.profile_draft,
    }, 520);
  }
  return api.post("/onboarding/chat", { message }).then((r) => r.data.data);
};

export const restartOnboarding = () => {
  if (isDemoMode()) {
    demoOnboardingIndex = 0;
    demoOnboardingCompleted = false;
    demoOnboardingDraft = {};
    try {
      localStorage.removeItem("zhiyao_onboarding_completed");
    } catch {}
    return delay(buildDemoOnboardingStatus());
  }
  return api.post("/onboarding/restart").then((r) => r.data.data);
};

// ---- Daily Check-in ----
export const createCheckIn = (content: string) => {
  if (isDemoMode()) {
    const checkIn: CheckIn = {
      id: `checkin-${Date.now()}`,
      raw_content: content,
      ai_summary: "我已经把今天的学习记录整理好了。你完成的内容会进入知识库，薄弱点会进入后续复习和 quiz 队列。",
      parsed_updates: {
        kps_created: [
          { name: "今日课堂新知识", subject: "综合", mastery_status: "learning" },
          { name: "待巩固薄弱点", subject: "综合", mastery_status: "reviewing" },
        ],
        kp_updates: [
          { kp_id: "demo-kp-1", new_mastery: "reviewing", reason: "用户主动提到今天复习或完成相关内容" },
        ],
        tasks_created: [
          { title: "根据今日内容生成 5 道小测", subject: "综合", estimated_minutes: 12 },
          { title: "明天复盘今日薄弱点", subject: "综合", estimated_minutes: 18 },
        ],
      },
      created_at: new Date().toISOString(),
    };
    demoCheckIns = [checkIn, ...demoCheckIns];
    return delay(checkIn, 760);
  }
  return api.post("/checkin", { content }).then((r) => r.data.data);
};

export const getTodayCheckIn = () => {
  if (isDemoMode()) return delay(demoCheckIns[0] ?? null);
  return api.get("/checkin/today").then((r) => r.data.data);
};

export const listCheckIns = (page = 1, page_size = 20) => {
  if (isDemoMode()) return delay({ items: demoCheckIns, total: demoCheckIns.length, page, page_size });
  return api.get(`/checkin/history?page=${page}&page_size=${page_size}`).then((r) => r.data.data);
};

export async function streamAgentChat(
  message: string,
  session_id?: string | null,
  handlers: AgentChatHandlers = {}
) {
  if (isDemoMode()) {
    const reply = "我会根据你的知识点、任务和目标，帮你整理今天的学习进展并安排下一步。";
    handlers.onDelta?.(reply);
    const done = { done: true as const, session_id: session_id ?? `demo-agent-${Date.now()}`, tools_called: [] };
    handlers.onDone?.(done);
    return done;
  }

  const token = isBrowser() ? localStorage.getItem("access_token") : null;
  const response = await fetch(`${API_BASE}/agent/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, ...(session_id ? { session_id } : {}) }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Agent request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let doneEvent: Extract<AgentChatEvent, { done: true }> | null = null;

  function consumeChunk(chunk: string) {
    buffer += chunk;
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const dataLines = part
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim());

      for (const raw of dataLines) {
        if (!raw || raw === "[DONE]") continue;
        const event = JSON.parse(raw) as AgentChatEvent;
        if ("thinking" in event) handlers.onThinking?.(event.thinking);
        if ("delta" in event) handlers.onDelta?.(event.delta);
        if ("error" in event) handlers.onError?.(event.error);
        if ("done" in event) {
          doneEvent = event;
          handlers.onDone?.(event);
        }
      }
    }
  }

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    consumeChunk(decoder.decode(value, { stream: true }));
  }
  consumeChunk(decoder.decode());

  return doneEvent ?? { done: true as const, session_id: session_id ?? "", tools_called: [] };
}

// ---- Mistakes ----
export const listMistakes = (params?: { subject?: string; page?: number; page_size?: number }) => {
  if (isDemoMode()) {
    return delay([
      { id: "m-1", question_text: "质量为 2kg 的物体在水平面做匀速运动，μ=0.3，g=10m/s²，求摩擦力。", user_answer: "6N", reference_answer: "f = μmg = 0.3×2×10 = 6N，匀速则合力为零。", ai_feedback: "公式选择正确，但注意说明匀速运动中合力为零的物理意义。", ai_score: 72, bloom_level: "apply", question_type: "calculation", created_at: new Date().toISOString() },
      { id: "m-2", question_text: "f(x)=x³-3x 的单调递增区间。", user_answer: "(-∞,-1) 和 (1,+∞)", reference_answer: "f'(x)=3x²-3>0 → x<-1 或 x>1，单调递增区间为 (-∞,-1) 和 (1,+∞)。", ai_feedback: "结果正确，注意使用开区间表示。", ai_score: 88, bloom_level: "analyze", question_type: "calculation", created_at: new Date().toISOString() },
      { id: "m-3", question_text: "下列属于电解质的是：A.NaCl B.蔗糖 C.酒精 D.铁", user_answer: "D", reference_answer: "A. NaCl。铁是单质，不属于电解质或非电解质范畴。", ai_feedback: "混淆了单质与电解质的概念，电解质必须是化合物。", ai_score: 30, bloom_level: "remember", question_type: "fill_blank", created_at: new Date().toISOString() },
    ]);
  }
  return api.get("/mistakes", { params }).then((r) => r.data.data.items ?? r.data.data);
};

export const retryMistake = (id: string) => {
  if (isDemoMode()) return delay({ retry_question_id: `retry-${id}`, original_question_id: id, question_type: "calculation", bloom_level: "apply", question_text: "变式题：同一知识点的新题目，请重新作答……" });
  return api.post(`/mistakes/${id}/retry`).then((r) => r.data.data);
};

export const submitRetryAnswer = (questionId: string, retryQuestionId: string, userAnswer: string) => {
  if (isDemoMode()) return delay({ retry_question_id: retryQuestionId, ai_score: 85, ai_feedback: "理解有明显进步！", reference_answer: "参考答案示例……", mistake_resolved: true });
  return api.post(`/mistakes/${questionId}/retry/${retryQuestionId}/answer`, { user_answer: userAnswer }).then((r) => r.data.data);
};

export const removeMistake = (id: string) => {
  if (isDemoMode()) return delay({ success: true });
  return api.delete(`/mistakes/${id}`).then((r) => r.data.data);
};

// ---- Auth ----
export const login = (body: object) => {
  if (isDemoMode()) {
    return delay({
      access_token: "demo-token",
      token_type: "bearer",
      user: { id: "demo-user", username: "demo", nickname: "知曜体验用户" },
      request: body,
    });
  }
  return api.post("/auth/login", body).then((r) => r.data.data);
};

export const register = (body: object) => {
  if (isDemoMode()) {
    return delay({ id: "demo-user", username: "demo", nickname: "知曜体验用户", request: body });
  }
  return api.post("/auth/register", body).then((r) => r.data.data);
};

export const getMe = () => {
  if (isDemoMode()) return delay({ id: "demo-user", username: "demo", nickname: "知曜体验用户" });
  return api.get("/auth/me").then((r) => r.data.data);
};
