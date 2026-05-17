import axios from "axios";

const DEFAULT_API_BASE = "http://localhost:8000/v1";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE;

type DemoTask = {
  id: string;
  title: string;
  task_type: string;
  subject?: string;
  estimated_minutes?: number;
  priority?: string;
  is_done: boolean;
  ai_reason?: string;
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

const isBrowser = () => typeof window !== "undefined";

const isLocalHost = (hostname: string) =>
  ["localhost", "127.0.0.1", "::1"].includes(hostname);

const apiBaseIsLocal = () =>
  API_BASE.includes("localhost") || API_BASE.includes("127.0.0.1");

export function isDemoMode() {
  if (process.env.NEXT_PUBLIC_DEMO_MODE === "true") return true;
  if (!isBrowser()) return false;

  const localOverride = (() => {
    try {
      return window.localStorage?.getItem("zhiyao_demo_mode") === "true";
    } catch {
      return false;
    }
  })();
  const externalViewerUsingLocalApi = apiBaseIsLocal() && !isLocalHost(window.location.hostname);

  return localOverride || externalViewerUsingLocalApi;
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
    ai_reason: "12张到期卡已等待复习，间隔重复效果最佳，控制在25分钟内完成。",
  },
  {
    id: "task-2",
    title: "错题重练：物理受力分析（3题）",
    task_type: "mistake_review",
    subject: "物理",
    estimated_minutes: 18,
    priority: "high",
    is_done: false,
    ai_reason: "受力分析是本周错误率最高的考点，3道重练题可精准校准掌握度。",
  },
  {
    id: "task-3",
    title: "整理英语阅读高频词",
    task_type: "manual",
    subject: "英语",
    estimated_minutes: 16,
    priority: "normal",
    is_done: true,
    ai_reason: "已识别出8个可沉淀为闪卡的高频词，整理后直接生成复习队列。",
  },
  {
    id: "task-4",
    title: "预习化学氧化还原反应",
    task_type: "manual",
    subject: "化学",
    estimated_minutes: 25,
    priority: "normal",
    is_done: false,
    ai_reason: "化学知识点积累偏少，今天预习可为后续闪卡和训练打好基础。",
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
    if (err.response?.status === 401 && isBrowser()) {
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
    demoTasks = demoTasks.map((task) => (task.id === id ? { ...task, ...body } : task));
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
  return api.get("/progress/weekly").then((r) => r.data.data);
};

// ---- Notes ----
export const listNotes = (page = 1) => {
  if (isDemoMode()) return delay(page === 1 ? demoNotes : []);
  return api.get(`/notes?page=${page}`).then((r) => r.data.data);
};

export const generateNote = (body: { topic?: string; subject?: string; [key: string]: unknown }) => {
  if (isDemoMode()) {
    const topic = body.topic?.trim() || "AI 整理学习笔记";
    const note = {
      id: `note-${Date.now()}`,
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

// ---- Flashcards ----
export const getDueCards = (page = 1) => {
  if (isDemoMode()) return delay(page === 1 ? demoCards : []);
  return api.get(`/flashcards/due?page=${page}`).then((r) => r.data.data);
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

export const getKPStats = () => {
  if (isDemoMode()) return delay({ total: 4, new: 0, learning: 2, reviewing: 2, mastered: 0, by_subject: {} });
  return api.get("/knowledge-points/stats").then((r) => r.data.data);
};

// ---- Training ----
export const startTraining = (body: object) => {
  if (isDemoMode()) {
    return delay({
      session_id: "demo-training-1",
      subject: "物理",
      bloom_level: 3,
      question_count: 5,
      config: body,
    });
  }
  return api.post("/training/start", body).then((r) => r.data.data);
};

export const submitAnswer = (sessionId: string, questionId: string, body: object) => {
  if (isDemoMode()) {
    return delay({
      session_id: sessionId,
      question_id: questionId,
      answer: body,
      score: 84,
      feedback: "思路清晰，关键公式选择正确。建议补充单位和中间步骤，方便后续复盘。",
    });
  }
  return api.post(`/training/${sessionId}/answer/${questionId}`, body).then((r) => r.data.data);
};

// ---- Guidance ----
export const startGuidance = (body: { question: string; subject?: string }) => {
  if (isDemoMode()) {
    return delay({
      session_id: "demo-guid-1",
      message: { id: "msg-1", role: "assistant", content: "好问题！在我解释之前，我想先了解一下你目前对这个概念的理解——你能用自己的话描述一下它大概是什么吗？" },
    });
  }
  return api.post("/guidance/sessions", body).then((r) => r.data.data);
};

export const chatGuidance = (sessionId: string, message: string) => {
  if (isDemoMode()) {
    return delay({
      session_id: sessionId,
      message: { id: Date.now().toString(), role: "assistant", content: "很好，你提到了关键点。那你觉得，如果把这个条件去掉，结果会发生什么变化呢？" },
    });
  }
  return api.post(`/guidance/sessions/${sessionId}/chat`, { message }).then((r) => r.data.data);
};

export const listGuidanceSessions = (page = 1) => {
  if (isDemoMode()) return delay({ items: [], total: 0 });
  return api.get(`/guidance/sessions?page=${page}`).then((r) => r.data.data);
};

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
