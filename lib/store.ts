"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface User {
  id: string;
  username: string;
  nickname?: string;
  grade?: string;
  subjects?: string[];
}

interface AuthStore {
  user: User | null;
  token: string | null;
  learningGoal: string | null;   // 用户学习目标，onboarding 时填写
  setAuth: (user: User, token: string) => void;
  clearAuth: () => void;
  setLearningGoal: (goal: string) => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      learningGoal: null,
      setAuth: (user, token) => {
        try {
          localStorage.setItem("access_token", token);
        } catch {
          // Some preview surfaces can restrict storage; Zustand state still keeps the session.
        }
        set({ user, token });
      },
      clearAuth: () => {
        try {
          localStorage.removeItem("access_token");
        } catch {
          // Ignore storage cleanup failures in restricted preview surfaces.
        }
        set({ user: null, token: null, learningGoal: null });
      },
      setLearningGoal: (goal) => set({ learningGoal: goal }),
    }),
    { name: "zhiyao-auth" }
  )
);
