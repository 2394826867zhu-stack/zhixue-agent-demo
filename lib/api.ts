import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/v1";

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// ---- Progress ----
export const getOverview = () => api.get("/progress/overview").then((r) => r.data.data);
export const getHeatmap = (days = 90) => api.get(`/progress/heatmap?days=${days}`).then((r) => r.data.data);
export const getSubjects = () => api.get("/progress/subjects").then((r) => r.data.data);
export const getWeeklyReport = (offset = 0) => api.get(`/progress/weekly-report?offset_weeks=${offset}`).then((r) => r.data.data);

// ---- Tasks ----
export const getTodayTasks = () => api.get("/tasks").then((r) => r.data.data);
export const generateTasks = () => api.post("/tasks/generate").then((r) => r.data.data);
export const updateTask = (id: string, body: object) => api.patch(`/tasks/${id}`, body).then((r) => r.data.data);
export const getPomodoroStats = () => api.get("/tasks/pomodoro/stats").then((r) => r.data.data);

// ---- Notes ----
export const listNotes = (page = 1) => api.get(`/notes?page=${page}`).then((r) => r.data.data);
export const generateNote = (body: object) => api.post("/notes/generate", body).then((r) => r.data.data);

// ---- Flashcards ----
export const getDueCards = (page = 1) => api.get(`/flashcards/due?page=${page}`).then((r) => r.data.data);
export const reviewCard = (id: string, rating: number) => api.post(`/flashcards/${id}/review`, { rating }).then((r) => r.data.data);

// ---- Knowledge Points ----
export const listKPs = (params?: object) => api.get("/knowledge-points", { params }).then((r) => r.data.data);
export const getKPStats = () => api.get("/knowledge-points/stats").then((r) => r.data.data);

// ---- Training ----
export const startTraining = (body: object) => api.post("/training/start", body).then((r) => r.data.data);
export const submitAnswer = (sessionId: string, questionId: string, body: object) =>
  api.post(`/training/${sessionId}/answer/${questionId}`, body).then((r) => r.data.data);

// ---- Guidance ----
export const startGuidance = (body: object) => api.post("/guidance/sessions", body).then((r) => r.data.data);
export const chatGuidance = (sessionId: string, body: object) =>
  api.post(`/guidance/sessions/${sessionId}/chat`, body).then((r) => r.data.data);

// ---- Auth ----
export const login = (body: object) => api.post("/auth/login", body).then((r) => r.data.data);
export const register = (body: object) => api.post("/auth/register", body).then((r) => r.data.data);
export const getMe = () => api.get("/auth/me").then((r) => r.data.data);
