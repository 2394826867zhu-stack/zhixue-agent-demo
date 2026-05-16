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
  setAuth: (user: User, token: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      setAuth: (user, token) => {
        localStorage.setItem("access_token", token);
        set({ user, token });
      },
      clearAuth: () => {
        localStorage.removeItem("access_token");
        set({ user: null, token: null });
      },
    }),
    { name: "zhiyao-auth" }
  )
);
