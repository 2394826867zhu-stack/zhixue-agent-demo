# V2 Mobile App Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable V2 mobile learning loop and a parallel gamification lab that validates rewards, shop, and Agent equipment.

**Architecture:** Create two sibling Expo workspaces beside the existing frontend: `zhiyao-mobile-app` for the production mobile app and `zhiyao-gamification-lab` for reward-system exploration. The main app owns navigation, API integration, StudySpace, and lightweight reward display; the lab owns reward rules, avatar equipment, shop UI, and high-energy feedback experiments that can be promoted back into the app through clean package boundaries.

**Tech Stack:** Expo, React Native, TypeScript, Expo Router, TanStack Query, Zustand, React Native Reanimated, Expo Haptics, Jest, React Native Testing Library.

---

## File Structure

Create these sibling projects under `C:/Users/18208/Desktop/知曜创业项目/`.

```txt
zhiyao-mobile-app/
  app/
    _layout.tsx
    index.tsx
    tasks.tsx
    learn.tsx
    profile.tsx
    studyspace/[sessionId].tsx
  src/
    features/agent/AgentAvatar.tsx
    features/agent/agentState.ts
    features/home/HomeScreen.tsx
    features/learn/LearnScreen.tsx
    features/learn/CurriculumList.tsx
    features/studyspace/StudySpaceScreen.tsx
    features/studyspace/studyspaceTypes.ts
    features/tasks/TasksScreen.tsx
    features/profile/ProfileScreen.tsx
    features/rewards/RewardToast.tsx
    features/rewards/rewardTypes.ts
    shared/api/client.ts
    shared/api/curriculum.ts
    shared/api/studyspace.ts
    shared/api/stars.ts
    shared/api/cosmetics.ts
    shared/api/tasks.ts
    shared/theme/tokens.ts
    shared/ui/PressableScale.tsx
    shared/ui/SystemCard.tsx
    shared/ui/SystemText.tsx
    shared/motion/motionTokens.ts
  __tests__/
    rewardTypes.test.ts
    studyspaceFlow.test.ts

zhiyao-gamification-lab/
  apps/demo-expo/
    app/_layout.tsx
    app/index.tsx
    src/screens/LabHomeScreen.tsx
  packages/reward-engine/
    src/index.ts
    src/rewardRules.ts
    src/rewardRules.test.ts
    package.json
  packages/avatar-kit/
    src/index.ts
    src/avatarTypes.ts
    src/equipment.ts
    src/equipment.test.ts
    package.json
  packages/ui-rewards/
    src/index.ts
    src/RewardBurst.tsx
    src/ShopShelf.tsx
    package.json
```

The existing `zhiyao-frontend` remains a reference project. Do not migrate all V1 pages in Phase 1.

## Task 1: Scaffold The Two Expo Workspaces

**Files:**
- Create: `C:/Users/18208/Desktop/知曜创业项目/zhiyao-mobile-app/package.json`
- Create: `C:/Users/18208/Desktop/知曜创业项目/zhiyao-mobile-app/app/_layout.tsx`
- Create: `C:/Users/18208/Desktop/知曜创业项目/zhiyao-mobile-app/app/index.tsx`
- Create: `C:/Users/18208/Desktop/知曜创业项目/zhiyao-gamification-lab/package.json`
- Create: `C:/Users/18208/Desktop/知曜创业项目/zhiyao-gamification-lab/apps/demo-expo/app/_layout.tsx`
- Create: `C:/Users/18208/Desktop/知曜创业项目/zhiyao-gamification-lab/apps/demo-expo/app/index.tsx`

- [ ] **Step 1: Create the main Expo app**

Run from `C:/Users/18208/Desktop/知曜创业项目`:

```powershell
npx create-expo-app@latest zhiyao-mobile-app --template blank-typescript
```

Expected: a new `zhiyao-mobile-app` folder with `package.json`, `App.tsx`, and TypeScript config.

- [ ] **Step 2: Add app dependencies**

Run from `C:/Users/18208/Desktop/知曜创业项目/zhiyao-mobile-app`:

```powershell
npx expo install expo-router react-native-safe-area-context react-native-screens expo-haptics
npx expo install react-native-reanimated react-native-gesture-handler
npm install @tanstack/react-query zustand axios lucide-react-native
npm install -D jest @testing-library/react-native @types/jest
```

Expected: install completes and `package.json` includes Expo Router, Query, Zustand, Reanimated, Haptics, Axios, and testing libraries.

- [ ] **Step 3: Configure Expo Router entry**

Modify `C:/Users/18208/Desktop/知曜创业项目/zhiyao-mobile-app/package.json` so the main field is:

```json
{
  "main": "expo-router/entry"
}
```

Preserve the generated scripts and dependencies.

- [ ] **Step 4: Create the gamification lab workspace**

Run from `C:/Users/18208/Desktop/知曜创业项目`:

```powershell
New-Item -ItemType Directory -Force -Path zhiyao-gamification-lab/apps | Out-Null
Set-Location zhiyao-gamification-lab/apps
npx create-expo-app@latest demo-expo --template blank-typescript
```

Expected: `zhiyao-gamification-lab/apps/demo-expo` exists and runs as an Expo app.

- [ ] **Step 5: Add lab root workspace package**

Create `C:/Users/18208/Desktop/知曜创业项目/zhiyao-gamification-lab/package.json`:

```json
{
  "name": "zhiyao-gamification-lab",
  "private": true,
  "workspaces": [
    "apps/*",
    "packages/*"
  ],
  "scripts": {
    "test": "npm test --workspaces --if-present",
    "demo": "npm --workspace apps/demo-expo run start"
  }
}
```

- [ ] **Step 6: Verify both apps start**

Run:

```powershell
cd C:/Users/18208/Desktop/知曜创业项目/zhiyao-mobile-app
npx expo start --clear
```

Expected: Expo CLI starts and prints a local URL or QR code. Stop it with `Ctrl+C`.

Run:

```powershell
cd C:/Users/18208/Desktop/知曜创业项目/zhiyao-gamification-lab/apps/demo-expo
npx expo start --clear
```

Expected: Expo CLI starts and prints a local URL or QR code. Stop it with `Ctrl+C`.

- [ ] **Step 7: Commit scaffold**

Run from `C:/Users/18208/Desktop/知曜创业项目`:

```powershell
git -C zhiyao-mobile-app status --short
git -C zhiyao-gamification-lab status --short
```

If each new project is its own repository, commit inside each project:

```powershell
git add .
git commit -m "chore: scaffold v2 expo workspace"
```

If they are plain folders, leave them uncommitted until repository ownership is decided.

## Task 2: Build Shared Theme, Motion, And Primitive UI

**Files:**
- Create: `zhiyao-mobile-app/src/shared/theme/tokens.ts`
- Create: `zhiyao-mobile-app/src/shared/motion/motionTokens.ts`
- Create: `zhiyao-mobile-app/src/shared/ui/SystemText.tsx`
- Create: `zhiyao-mobile-app/src/shared/ui/SystemCard.tsx`
- Create: `zhiyao-mobile-app/src/shared/ui/PressableScale.tsx`
- Test: `zhiyao-mobile-app/__tests__/themeTokens.test.ts`

- [ ] **Step 1: Write token tests**

Create `__tests__/themeTokens.test.ts`:

```ts
import { colors, spacing, radius } from "../src/shared/theme/tokens";
import { motion } from "../src/shared/motion/motionTokens";

describe("V2 design tokens", () => {
  it("keeps the Apple-first base calm and the reward colors distinct", () => {
    expect(colors.surface).toBe("#F8FAFC");
    expect(colors.primary).toBe("#35D3B4");
    expect(colors.rewardGold).toBe("#F6C453");
    expect(colors.rewardPurple).toBe("#A78BFA");
    expect(colors.rewardBlue).toBe("#60A5FA");
  });

  it("uses stable touch-friendly spacing and radius values", () => {
    expect(spacing.touchTarget).toBe(44);
    expect(radius.sheet).toBe(28);
    expect(motion.pressMs).toBeLessThanOrEqual(150);
    expect(motion.complexMs).toBeLessThanOrEqual(400);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run from `zhiyao-mobile-app`:

```powershell
npm test -- --runTestsByPath __tests__/themeTokens.test.ts
```

Expected: FAIL because `tokens.ts` and `motionTokens.ts` do not exist.

- [ ] **Step 3: Add theme tokens**

Create `src/shared/theme/tokens.ts`:

```ts
export const colors = {
  background: "#FFFFFF",
  surface: "#F8FAFC",
  surfaceElevated: "#FFFFFF",
  textPrimary: "#0F172A",
  textSecondary: "#64748B",
  border: "#E2E8F0",
  primary: "#35D3B4",
  primaryPressed: "#22B99D",
  rewardGold: "#F6C453",
  rewardPurple: "#A78BFA",
  rewardBlue: "#60A5FA",
  success: "#34D399",
  warning: "#F59E0B",
  danger: "#EF4444"
} as const;

export const spacing = {
  xxs: 4,
  xs: 8,
  sm: 12,
  md: 16,
  lg: 24,
  xl: 32,
  touchTarget: 44
} as const;

export const radius = {
  card: 18,
  panel: 24,
  sheet: 28,
  pill: 999
} as const;
```

- [ ] **Step 4: Add motion tokens**

Create `src/shared/motion/motionTokens.ts`:

```ts
export const motion = {
  pressMs: 120,
  microMs: 180,
  transitionMs: 260,
  complexMs: 380,
  springDamping: 18,
  springMass: 0.8,
  springStiffness: 180
} as const;
```

- [ ] **Step 5: Add primitive text and card components**

Create `src/shared/ui/SystemText.tsx`:

```tsx
import { Text, TextProps, StyleSheet } from "react-native";
import { colors } from "../theme/tokens";

type Variant = "title" | "section" | "body" | "meta";

export function SystemText({ variant = "body", style, ...props }: TextProps & { variant?: Variant }) {
  return <Text {...props} style={[styles[variant], style]} />;
}

const styles = StyleSheet.create({
  title: { color: colors.textPrimary, fontSize: 28, lineHeight: 34, fontWeight: "700" },
  section: { color: colors.textPrimary, fontSize: 18, lineHeight: 24, fontWeight: "700" },
  body: { color: colors.textPrimary, fontSize: 16, lineHeight: 24, fontWeight: "400" },
  meta: { color: colors.textSecondary, fontSize: 13, lineHeight: 18, fontWeight: "500" }
});
```

Create `src/shared/ui/SystemCard.tsx`:

```tsx
import { PropsWithChildren } from "react";
import { StyleSheet, View, ViewProps } from "react-native";
import { colors, radius, spacing } from "../theme/tokens";

export function SystemCard({ children, style, ...props }: PropsWithChildren<ViewProps>) {
  return (
    <View {...props} style={[styles.card, style]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.card,
    padding: spacing.md
  }
});
```

Create `src/shared/ui/PressableScale.tsx`:

```tsx
import { PropsWithChildren } from "react";
import { Pressable, PressableProps } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import * as Haptics from "expo-haptics";
import { motion } from "../motion/motionTokens";

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

export function PressableScale({ children, onPress, ...props }: PropsWithChildren<PressableProps>) {
  const scale = useSharedValue(1);
  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  return (
    <AnimatedPressable
      {...props}
      onPressIn={() => {
        scale.value = withTiming(0.97, { duration: motion.pressMs });
      }}
      onPressOut={() => {
        scale.value = withTiming(1, { duration: motion.pressMs });
      }}
      onPress={(event) => {
        Haptics.selectionAsync();
        onPress?.(event);
      }}
      style={[animatedStyle, props.style]}
    >
      {children}
    </AnimatedPressable>
  );
}
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```powershell
npm test -- --runTestsByPath __tests__/themeTokens.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit theme primitives**

```powershell
git add src/shared __tests__/themeTokens.test.ts
git commit -m "feat: add v2 mobile design primitives"
```

## Task 3: Add API Clients And Phase 1 Types

**Files:**
- Create: `zhiyao-mobile-app/src/shared/api/client.ts`
- Create: `zhiyao-mobile-app/src/shared/api/curriculum.ts`
- Create: `zhiyao-mobile-app/src/shared/api/studyspace.ts`
- Create: `zhiyao-mobile-app/src/shared/api/stars.ts`
- Create: `zhiyao-mobile-app/src/shared/api/cosmetics.ts`
- Create: `zhiyao-mobile-app/src/shared/api/tasks.ts`
- Create: `zhiyao-mobile-app/src/features/studyspace/studyspaceTypes.ts`
- Create: `zhiyao-mobile-app/src/features/rewards/rewardTypes.ts`
- Test: `zhiyao-mobile-app/__tests__/studyspaceFlow.test.ts`
- Test: `zhiyao-mobile-app/__tests__/rewardTypes.test.ts`

- [ ] **Step 1: Write type tests**

Create `__tests__/rewardTypes.test.ts`:

```ts
import { classifyKnowledgeCard, type KnowledgePriorityInput } from "../src/features/rewards/rewardTypes";

describe("knowledge card priority", () => {
  it("classifies high-value risky knowledge as gold", () => {
    const input: KnowledgePriorityInput = {
      difficulty: 5,
      importance: 5,
      mastery: 32,
      forgettingRisk: 0.8,
      examRelated: true,
      mistakeCount: 3
    };

    expect(classifyKnowledgeCard(input)).toEqual({
      tier: "gold",
      label: "金卡",
      agentReason: "这张卡关联考试、错题和遗忘风险，我会优先陪你处理它。"
    });
  });
});
```

Create `__tests__/studyspaceFlow.test.ts`:

```ts
import { getNextLessonLabel, type CompleteSessionResponse } from "../src/features/studyspace/studyspaceTypes";

describe("studyspace completion", () => {
  it("summarizes the next unlocked lesson", () => {
    const response: CompleteSessionResponse = {
      session_id: "session-1",
      kp_extracted: 3,
      flashcards_created: 6,
      stars_earned: 18,
      next_lesson: {
        id: "chapter-2",
        subject: "数学",
        grade_type: "senior_high",
        grade_year: 2,
        semester: 1,
        chapter_index: 1,
        chapter_title: "函数",
        lesson_index: 2,
        lesson_title: "函数图像",
        textbook_version: "通用",
        is_key: true
      }
    };

    expect(getNextLessonLabel(response)).toBe("已解锁：函数图像");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
npm test -- --runTestsByPath __tests__/rewardTypes.test.ts __tests__/studyspaceFlow.test.ts
```

Expected: FAIL because the source files do not exist.

- [ ] **Step 3: Add reward and StudySpace types**

Create `src/features/rewards/rewardTypes.ts`:

```ts
export type KnowledgeTier = "gold" | "purple" | "blue";

export type KnowledgePriorityInput = {
  difficulty: 1 | 2 | 3 | 4 | 5;
  importance: 1 | 2 | 3 | 4 | 5;
  mastery: number;
  forgettingRisk: number;
  examRelated: boolean;
  mistakeCount: number;
};

export type KnowledgeCardClassification = {
  tier: KnowledgeTier;
  label: "金卡" | "紫卡" | "蓝卡";
  agentReason: string;
};

export function classifyKnowledgeCard(input: KnowledgePriorityInput): KnowledgeCardClassification {
  const score =
    input.difficulty * 1.1 +
    input.importance * 1.4 +
    (100 - input.mastery) / 20 +
    input.forgettingRisk * 4 +
    (input.examRelated ? 3 : 0) +
    Math.min(input.mistakeCount, 4);

  if (score >= 19) {
    return {
      tier: "gold",
      label: "金卡",
      agentReason: "这张卡关联考试、错题和遗忘风险，我会优先陪你处理它。"
    };
  }

  if (score >= 13) {
    return {
      tier: "purple",
      label: "紫卡",
      agentReason: "这张卡最近值得巩固，我会把它放进进阶复习。"
    };
  }

  return {
    tier: "blue",
    label: "蓝卡",
    agentReason: "这张卡适合快速回看，用来稳住基础。"
  };
}
```

Create `src/features/studyspace/studyspaceTypes.ts`:

```ts
export type CurriculumChapter = {
  id: string;
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

export type StudySpaceSession = {
  id: string;
  chapter_id: string;
  chapter_title: string;
  lesson_title: string;
  subject: string;
  status: "active" | "paused" | "completed";
  progress: number;
  agent_session_id: string | null;
  started_at: string;
  completed_at: string | null;
};

export type CompleteSessionResponse = {
  session_id: string;
  kp_extracted: number;
  flashcards_created: number;
  stars_earned: number;
  next_lesson: CurriculumChapter | null;
};

export function getNextLessonLabel(response: CompleteSessionResponse): string {
  return response.next_lesson ? `已解锁：${response.next_lesson.lesson_title}` : "本阶段已经完成";
}
```

- [ ] **Step 4: Add API client**

Create `src/shared/api/client.ts`:

```ts
import axios from "axios";

export const api = axios.create({
  baseURL: process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000/v1",
  timeout: 20000
});

export function setAccessToken(token: string | null) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

export async function unwrapData<T>(promise: Promise<{ data: { data: T } }>): Promise<T> {
  const response = await promise;
  return response.data.data;
}
```

Create `src/shared/api/curriculum.ts`:

```ts
import { unwrapData, api } from "./client";
import type { CurriculumChapter } from "../../features/studyspace/studyspaceTypes";

export function getCurriculumChapters(params: { subject?: string; grade_type?: string }) {
  return unwrapData<CurriculumChapter[]>(api.get("/curriculum/chapters", { params }));
}
```

Create `src/shared/api/studyspace.ts`:

```ts
import { unwrapData, api } from "./client";
import type { CompleteSessionResponse, StudySpaceSession } from "../../features/studyspace/studyspaceTypes";

export function startStudySpaceSession(chapterId: string) {
  return unwrapData<StudySpaceSession>(api.post("/studyspace/sessions", { chapter_id: chapterId }));
}

export function getStudySpaceSession(sessionId: string) {
  return unwrapData<StudySpaceSession>(api.get(`/studyspace/sessions/${sessionId}`));
}

export function completeStudySpaceSession(sessionId: string) {
  return unwrapData<CompleteSessionResponse>(api.post(`/studyspace/sessions/${sessionId}/complete`));
}
```

Create `src/shared/api/stars.ts`:

```ts
import { unwrapData, api } from "./client";

export type StarBalance = {
  balance: number;
  total_earned: number;
  total_spent: number;
};

export function getStarBalance() {
  return unwrapData<StarBalance>(api.get("/stars/balance"));
}
```

Create `src/shared/api/cosmetics.ts`:

```ts
import { unwrapData, api } from "./client";

export type CosmeticItem = {
  id: string;
  name: string;
  category: "material" | "accessory" | "aura" | "voice";
  description: string;
  price: number;
  preview_url: string;
  is_unlocked: boolean;
  is_equipped: boolean;
};

export function getCosmeticsShop() {
  return unwrapData<CosmeticItem[]>(api.get("/cosmetics/shop"));
}
```

Create `src/shared/api/tasks.ts`:

```ts
import { unwrapData, api } from "./client";

export type DailyTask = {
  id: string;
  title: string;
  subject: string | null;
  estimated_minutes: number;
  status: "todo" | "in_progress" | "done";
  priority: number;
  source: "system" | "user";
  auto_complete_trigger: "flashcard_session" | "lesson_complete" | "training_session" | null;
};

export function getTodayTasks() {
  return unwrapData<DailyTask[]>(api.get("/tasks/today"));
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```powershell
npm test -- --runTestsByPath __tests__/rewardTypes.test.ts __tests__/studyspaceFlow.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit API and type layer**

```powershell
git add src/shared/api src/features/rewards src/features/studyspace __tests__
git commit -m "feat: add v2 api and studyspace types"
```

## Task 4: Implement Navigation And Home System Hub

**Files:**
- Create: `zhiyao-mobile-app/app/_layout.tsx`
- Create: `zhiyao-mobile-app/app/index.tsx`
- Create: `zhiyao-mobile-app/app/tasks.tsx`
- Create: `zhiyao-mobile-app/app/learn.tsx`
- Create: `zhiyao-mobile-app/app/profile.tsx`
- Create: `zhiyao-mobile-app/src/features/agent/AgentAvatar.tsx`
- Create: `zhiyao-mobile-app/src/features/agent/agentState.ts`
- Create: `zhiyao-mobile-app/src/features/home/HomeScreen.tsx`
- Create: `zhiyao-mobile-app/src/features/tasks/TasksScreen.tsx`
- Create: `zhiyao-mobile-app/src/features/profile/ProfileScreen.tsx`

- [ ] **Step 1: Add Agent state definitions**

Create `src/features/agent/agentState.ts`:

```ts
export type AgentMood = "idle" | "thinking" | "speaking" | "focus" | "celebrate" | "remind" | "sleepy" | "confused";

export type AgentEquipment = {
  material: string | null;
  accessory: string | null;
  aura: string | null;
  voice: string | null;
};

export const defaultAgentEquipment: AgentEquipment = {
  material: null,
  accessory: null,
  aura: null,
  voice: null
};
```

- [ ] **Step 2: Add low-poly placeholder Agent**

Create `src/features/agent/AgentAvatar.tsx`:

```tsx
import { StyleSheet, View } from "react-native";
import Animated, { useAnimatedStyle, withRepeat, withSequence, withTiming, useSharedValue } from "react-native-reanimated";
import { useEffect } from "react";
import { colors, radius } from "../../shared/theme/tokens";
import type { AgentMood, AgentEquipment } from "./agentState";

export function AgentAvatar({ mood, equipment }: { mood: AgentMood; equipment: AgentEquipment }) {
  const float = useSharedValue(0);

  useEffect(() => {
    float.value = withRepeat(withSequence(withTiming(-6, { duration: 1200 }), withTiming(0, { duration: 1200 })), -1, true);
  }, [float]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: mood === "focus" ? 0 : float.value }]
  }));

  return (
    <Animated.View style={[styles.stage, animatedStyle]}>
      <View style={[styles.aura, equipment.aura ? styles.equippedAura : null]} />
      <View style={styles.head} />
      <View style={styles.body} />
      {equipment.accessory ? <View style={styles.accessory} /> : null}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  stage: {
    width: 132,
    height: 168,
    alignItems: "center",
    justifyContent: "center"
  },
  aura: {
    position: "absolute",
    width: 128,
    height: 128,
    borderRadius: 64,
    backgroundColor: "#DBEAFE"
  },
  equippedAura: {
    backgroundColor: "#FEF3C7"
  },
  head: {
    width: 78,
    height: 72,
    borderRadius: 26,
    backgroundColor: "#F9A8D4",
    borderWidth: 2,
    borderColor: "#FDE68A"
  },
  body: {
    width: 92,
    height: 76,
    marginTop: -8,
    borderRadius: radius.panel,
    backgroundColor: colors.primary
  },
  accessory: {
    position: "absolute",
    top: 28,
    width: 66,
    height: 14,
    borderRadius: 7,
    backgroundColor: colors.rewardGold
  }
});
```

- [ ] **Step 3: Add tab layout**

Create `app/_layout.tsx`:

```tsx
import { Tabs } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Home, ListChecks, GraduationCap, UserRound } from "lucide-react-native";
import { colors } from "../src/shared/theme/tokens";

const queryClient = new QueryClient();

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: colors.primaryPressed,
          tabBarInactiveTintColor: colors.textSecondary,
          tabBarStyle: { height: 64, paddingTop: 8, paddingBottom: 10 }
        }}
      >
        <Tabs.Screen name="index" options={{ title: "首页", tabBarIcon: ({ color }) => <Home color={color} size={22} /> }} />
        <Tabs.Screen name="tasks" options={{ title: "任务", tabBarIcon: ({ color }) => <ListChecks color={color} size={22} /> }} />
        <Tabs.Screen name="learn" options={{ title: "学习", tabBarIcon: ({ color }) => <GraduationCap color={color} size={22} /> }} />
        <Tabs.Screen name="profile" options={{ title: "我的", tabBarIcon: ({ color }) => <UserRound color={color} size={22} /> }} />
        <Tabs.Screen name="studyspace/[sessionId]" options={{ href: null }} />
      </Tabs>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 4: Add Home screen**

Create `src/features/home/HomeScreen.tsx`:

```tsx
import { StyleSheet, View } from "react-native";
import { router } from "expo-router";
import { AgentAvatar } from "../agent/AgentAvatar";
import { defaultAgentEquipment } from "../agent/agentState";
import { PressableScale } from "../../shared/ui/PressableScale";
import { SystemCard } from "../../shared/ui/SystemCard";
import { SystemText } from "../../shared/ui/SystemText";
import { colors, radius, spacing } from "../../shared/theme/tokens";

export function HomeScreen() {
  return (
    <View style={styles.screen}>
      <SystemText variant="title">知曜</SystemText>
      <View style={styles.agentPanel}>
        <AgentAvatar mood="speaking" equipment={defaultAgentEquipment} />
        <SystemCard style={styles.speech}>
          <SystemText variant="meta">Agent says</SystemText>
          <SystemText>我把今天拆成一节课和一次轻复习，先从学习页开始会比较顺。</SystemText>
          <PressableScale style={styles.primaryButton} onPress={() => router.push("/learn")}>
            <SystemText style={styles.primaryButtonText}>开始今日学习</SystemText>
          </PressableScale>
        </SystemCard>
      </View>
      <View style={styles.metricRow}>
        <SystemCard style={styles.metric}><SystemText variant="section">25</SystemText><SystemText variant="meta">分钟</SystemText></SystemCard>
        <SystemCard style={styles.metric}><SystemText variant="section">7</SystemText><SystemText variant="meta">连续</SystemText></SystemCard>
        <SystemCard style={styles.metric}><SystemText variant="section">12</SystemText><SystemText variant="meta">待复习</SystemText></SystemCard>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.surface,
    paddingTop: 64,
    paddingHorizontal: spacing.md,
    gap: spacing.md
  },
  agentPanel: {
    minHeight: 260,
    borderRadius: 32,
    padding: spacing.md,
    backgroundColor: "#ECFDF5",
    alignItems: "center",
    gap: spacing.sm
  },
  speech: {
    width: "100%",
    gap: spacing.sm
  },
  primaryButton: {
    minHeight: 48,
    borderRadius: radius.pill,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center"
  },
  primaryButtonText: {
    color: colors.textPrimary,
    fontWeight: "700"
  },
  metricRow: {
    flexDirection: "row",
    gap: spacing.sm
  },
  metric: {
    flex: 1,
    minHeight: 84,
    justifyContent: "center"
  }
});
```

- [ ] **Step 5: Wire route files**

Create `app/index.tsx`:

```tsx
import { HomeScreen } from "../src/features/home/HomeScreen";
export default HomeScreen;
```

Create `src/features/tasks/TasksScreen.tsx`:

```tsx
import { View } from "react-native";
import { SystemText } from "../../shared/ui/SystemText";
export function TasksScreen() {
  return <View style={{ flex: 1, padding: 24, paddingTop: 64 }}><SystemText variant="title">任务</SystemText></View>;
}
```

Create `app/tasks.tsx`:

```tsx
import { TasksScreen } from "../src/features/tasks/TasksScreen";
export default TasksScreen;
```

Create `src/features/profile/ProfileScreen.tsx`:

```tsx
import { View } from "react-native";
import { SystemText } from "../../shared/ui/SystemText";
export function ProfileScreen() {
  return <View style={{ flex: 1, padding: 24, paddingTop: 64 }}><SystemText variant="title">我的</SystemText></View>;
}
```

Create `app/profile.tsx`:

```tsx
import { ProfileScreen } from "../src/features/profile/ProfileScreen";
export default ProfileScreen;
```

- [ ] **Step 6: Verify navigation**

Run:

```powershell
npx expo start --clear
```

Expected: the app opens with four tabs: 首页, 任务, 学习, 我的. The 首页 button navigates to 学习 after Task 5 adds the screen.

- [ ] **Step 7: Commit navigation and home**

```powershell
git add app src/features src/shared
git commit -m "feat: add agent-first mobile navigation"
```

## Task 5: Implement Learn Screen And StudySpace Shell

**Files:**
- Create: `zhiyao-mobile-app/src/features/learn/LearnScreen.tsx`
- Create: `zhiyao-mobile-app/src/features/learn/CurriculumList.tsx`
- Create: `zhiyao-mobile-app/src/features/studyspace/StudySpaceScreen.tsx`
- Create: `zhiyao-mobile-app/app/learn.tsx`
- Create: `zhiyao-mobile-app/app/studyspace/[sessionId].tsx`

- [ ] **Step 1: Add curriculum list component**

Create `src/features/learn/CurriculumList.tsx`:

```tsx
import { StyleSheet, View } from "react-native";
import { router } from "expo-router";
import { PressableScale } from "../../shared/ui/PressableScale";
import { SystemCard } from "../../shared/ui/SystemCard";
import { SystemText } from "../../shared/ui/SystemText";
import { colors, spacing } from "../../shared/theme/tokens";

const sampleLessons = [
  { id: "demo-session-1", title: "函数的概念", status: "available" },
  { id: "demo-session-2", title: "函数图像", status: "locked" }
] as const;

export function CurriculumList() {
  return (
    <View style={styles.list}>
      {sampleLessons.map((lesson) => (
        <PressableScale key={lesson.id} disabled={lesson.status === "locked"} onPress={() => router.push(`/studyspace/${lesson.id}`)}>
          <SystemCard style={[styles.lesson, lesson.status === "locked" && styles.locked]}>
            <SystemText variant="section">{lesson.title}</SystemText>
            <SystemText variant="meta">{lesson.status === "available" ? "可进入 StudySpace" : "完成上一课后解锁"}</SystemText>
          </SystemCard>
        </PressableScale>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: spacing.sm },
  lesson: { gap: spacing.xs },
  locked: { opacity: 0.48, backgroundColor: colors.surface }
});
```

- [ ] **Step 2: Add Learn screen with Focus entry**

Create `src/features/learn/LearnScreen.tsx`:

```tsx
import { StyleSheet, View } from "react-native";
import { CurriculumList } from "./CurriculumList";
import { SystemCard } from "../../shared/ui/SystemCard";
import { SystemText } from "../../shared/ui/SystemText";
import { colors, spacing } from "../../shared/theme/tokens";

export function LearnScreen() {
  return (
    <View style={styles.screen}>
      <SystemText variant="title">学习</SystemText>
      <SystemCard style={styles.focusCard}>
        <SystemText variant="section">Focus 模式</SystemText>
        <SystemText variant="meta">安静专注：番茄钟 + Agent 陪伴</SystemText>
      </SystemCard>
      <SystemText variant="section">课程</SystemText>
      <CurriculumList />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.surface, paddingTop: 64, paddingHorizontal: spacing.md, gap: spacing.md },
  focusCard: { backgroundColor: "#F8FAFC", minHeight: 96, justifyContent: "center", gap: spacing.xs }
});
```

Create `app/learn.tsx`:

```tsx
import { LearnScreen } from "../src/features/learn/LearnScreen";
export default LearnScreen;
```

- [ ] **Step 3: Add StudySpace shell**

Create `src/features/studyspace/StudySpaceScreen.tsx`:

```tsx
import { StyleSheet, View } from "react-native";
import { AgentAvatar } from "../agent/AgentAvatar";
import { defaultAgentEquipment } from "../agent/agentState";
import { PressableScale } from "../../shared/ui/PressableScale";
import { SystemCard } from "../../shared/ui/SystemCard";
import { SystemText } from "../../shared/ui/SystemText";
import { colors, spacing } from "../../shared/theme/tokens";

export function StudySpaceScreen({ sessionId }: { sessionId: string }) {
  return (
    <View style={styles.screen}>
      <SystemText variant="meta">StudySpace · {sessionId}</SystemText>
      <SystemText variant="title">函数的概念</SystemText>
      <View style={styles.agentRow}>
        <AgentAvatar mood="thinking" equipment={defaultAgentEquipment} />
        <SystemCard style={styles.message}>
          <SystemText>我先带你抓住定义，再用一张图解释输入和输出。</SystemText>
        </SystemCard>
      </View>
      <SystemCard style={styles.toolPanel}>
        <SystemText variant="section">工具</SystemText>
        <SystemText variant="meta">上传资料 / 画板 / 闪卡 / 练习将在这里流出</SystemText>
      </SystemCard>
      <PressableScale style={styles.completeButton}>
        <SystemText style={styles.completeText}>完成课时</SystemText>
      </PressableScale>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.surface, paddingTop: 64, paddingHorizontal: spacing.md, gap: spacing.md },
  agentRow: { alignItems: "center", gap: spacing.sm },
  message: { width: "100%" },
  toolPanel: { minHeight: 112, gap: spacing.xs },
  completeButton: { minHeight: 52, backgroundColor: colors.primary, borderRadius: 999, alignItems: "center", justifyContent: "center" },
  completeText: { fontWeight: "700" }
});
```

Create `app/studyspace/[sessionId].tsx`:

```tsx
import { useLocalSearchParams } from "expo-router";
import { StudySpaceScreen } from "../../src/features/studyspace/StudySpaceScreen";

export default function StudySpaceRoute() {
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>();
  return <StudySpaceScreen sessionId={sessionId || "demo-session"} />;
}
```

- [ ] **Step 4: Verify learning route**

Run:

```powershell
npx expo start --clear
```

Expected: 首页 -> 开始今日学习 -> 学习. Tapping “函数的概念” opens StudySpace shell.

- [ ] **Step 5: Commit learning shell**

```powershell
git add app src/features/learn src/features/studyspace
git commit -m "feat: add learn and studyspace shell"
```

## Task 6: Add Completion Reward Feedback And Profile Assets

**Files:**
- Create: `zhiyao-mobile-app/src/features/rewards/RewardToast.tsx`
- Modify: `zhiyao-mobile-app/src/features/studyspace/StudySpaceScreen.tsx`
- Modify: `zhiyao-mobile-app/src/features/profile/ProfileScreen.tsx`

- [ ] **Step 1: Add reward toast component**

Create `src/features/rewards/RewardToast.tsx`:

```tsx
import { StyleSheet, View } from "react-native";
import Animated, { FadeInDown, FadeOutUp } from "react-native-reanimated";
import { SystemText } from "../../shared/ui/SystemText";
import { colors, radius, spacing } from "../../shared/theme/tokens";

export function RewardToast({ stars, nextLesson }: { stars: number; nextLesson: string }) {
  return (
    <Animated.View entering={FadeInDown.duration(240)} exiting={FadeOutUp.duration(180)} style={styles.toast}>
      <SystemText variant="section">+{stars} 知星</SystemText>
      <SystemText variant="meta">{nextLesson}</SystemText>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  toast: {
    position: "absolute",
    left: spacing.md,
    right: spacing.md,
    bottom: 24,
    borderRadius: radius.panel,
    backgroundColor: colors.rewardGold,
    padding: spacing.md,
    alignItems: "center",
    gap: spacing.xs
  }
});
```

- [ ] **Step 2: Wire completion feedback**

Modify `src/features/studyspace/StudySpaceScreen.tsx` so it tracks completion:

```tsx
import { useState } from "react";
import { StyleSheet, View } from "react-native";
import * as Haptics from "expo-haptics";
import { AgentAvatar } from "../agent/AgentAvatar";
import { defaultAgentEquipment } from "../agent/agentState";
import { RewardToast } from "../rewards/RewardToast";
import { PressableScale } from "../../shared/ui/PressableScale";
import { SystemCard } from "../../shared/ui/SystemCard";
import { SystemText } from "../../shared/ui/SystemText";
import { colors, spacing } from "../../shared/theme/tokens";

export function StudySpaceScreen({ sessionId }: { sessionId: string }) {
  const [completed, setCompleted] = useState(false);

  return (
    <View style={styles.screen}>
      <SystemText variant="meta">StudySpace · {sessionId}</SystemText>
      <SystemText variant="title">函数的概念</SystemText>
      <View style={styles.agentRow}>
        <AgentAvatar mood={completed ? "celebrate" : "thinking"} equipment={defaultAgentEquipment} />
        <SystemCard style={styles.message}>
          <SystemText>{completed ? "这节课收好了，我把下一课也替你点亮了。" : "我先带你抓住定义，再用一张图解释输入和输出。"}</SystemText>
        </SystemCard>
      </View>
      <SystemCard style={styles.toolPanel}>
        <SystemText variant="section">工具</SystemText>
        <SystemText variant="meta">上传资料 / 画板 / 闪卡 / 练习将在这里流出</SystemText>
      </SystemCard>
      <PressableScale
        style={styles.completeButton}
        onPress={() => {
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          setCompleted(true);
        }}
      >
        <SystemText style={styles.completeText}>完成课时</SystemText>
      </PressableScale>
      {completed ? <RewardToast stars={18} nextLesson="已解锁：函数图像" /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.surface, paddingTop: 64, paddingHorizontal: spacing.md, gap: spacing.md },
  agentRow: { alignItems: "center", gap: spacing.sm },
  message: { width: "100%" },
  toolPanel: { minHeight: 112, gap: spacing.xs },
  completeButton: { minHeight: 52, backgroundColor: colors.primary, borderRadius: 999, alignItems: "center", justifyContent: "center" },
  completeText: { fontWeight: "700" }
});
```

- [ ] **Step 3: Add profile assets screen**

Modify `src/features/profile/ProfileScreen.tsx`:

```tsx
import { StyleSheet, View } from "react-native";
import { AgentAvatar } from "../agent/AgentAvatar";
import { defaultAgentEquipment } from "../agent/agentState";
import { SystemCard } from "../../shared/ui/SystemCard";
import { SystemText } from "../../shared/ui/SystemText";
import { colors, spacing } from "../../shared/theme/tokens";

export function ProfileScreen() {
  return (
    <View style={styles.screen}>
      <SystemText variant="title">我的</SystemText>
      <SystemCard style={styles.agentCard}>
        <AgentAvatar mood="idle" equipment={{ ...defaultAgentEquipment, aura: "starter_aura", accessory: "gold_pin" }} />
        <SystemText variant="section">128 知星</SystemText>
        <SystemText variant="meta">当前装备：新手光环 · 金色胸针</SystemText>
      </SystemCard>
      <SystemCard>
        <SystemText variant="section">商店</SystemText>
        <SystemText variant="meta">更多装扮会从 Gamification Lab 回灌到这里。</SystemText>
      </SystemCard>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.surface, paddingTop: 64, paddingHorizontal: spacing.md, gap: spacing.md },
  agentCard: { alignItems: "center", gap: spacing.sm }
});
```

- [ ] **Step 4: Verify completion loop**

Run:

```powershell
npx expo start --clear
```

Expected: Enter StudySpace, tap 完成课时, see Agent celebration state and `+18 知星` reward toast. Profile shows balance and equipped starter items.

- [ ] **Step 5: Commit reward loop**

```powershell
git add src/features/rewards src/features/studyspace src/features/profile
git commit -m "feat: add studyspace reward feedback"
```

## Task 7: Build Gamification Lab Packages

**Files:**
- Create: `zhiyao-gamification-lab/packages/reward-engine/package.json`
- Create: `zhiyao-gamification-lab/packages/reward-engine/src/index.ts`
- Create: `zhiyao-gamification-lab/packages/reward-engine/src/rewardRules.ts`
- Create: `zhiyao-gamification-lab/packages/reward-engine/src/rewardRules.test.ts`
- Create: `zhiyao-gamification-lab/packages/avatar-kit/package.json`
- Create: `zhiyao-gamification-lab/packages/avatar-kit/src/index.ts`
- Create: `zhiyao-gamification-lab/packages/avatar-kit/src/avatarTypes.ts`
- Create: `zhiyao-gamification-lab/packages/avatar-kit/src/equipment.ts`
- Create: `zhiyao-gamification-lab/packages/avatar-kit/src/equipment.test.ts`

- [ ] **Step 1: Add reward engine package**

Create `packages/reward-engine/package.json`:

```json
{
  "name": "@zhiyao/reward-engine",
  "version": "0.1.0",
  "private": true,
  "main": "src/index.ts",
  "scripts": {
    "test": "jest"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "ts-jest": "^29.2.5",
    "typescript": "^5.0.0"
  }
}
```

Create `packages/reward-engine/src/rewardRules.test.ts`:

```ts
import { applyLearningEvent } from "./rewardRules";

describe("reward rules", () => {
  it("rewards lesson completion with stars, xp, and streak progress", () => {
    expect(applyLearningEvent({ type: "lesson_complete", baseMinutes: 25, streakDay: 7 })).toEqual({
      stars: 22,
      xp: 80,
      rarityProgress: 0.18,
      message: "课时完成，知星和连续奖励一起到账。"
    });
  });
});
```

Create `packages/reward-engine/src/rewardRules.ts`:

```ts
export type LearningEvent = {
  type: "lesson_complete" | "flashcard_review" | "focus_complete";
  baseMinutes: number;
  streakDay: number;
};

export type RewardResult = {
  stars: number;
  xp: number;
  rarityProgress: number;
  message: string;
};

export function applyLearningEvent(event: LearningEvent): RewardResult {
  const baseStars = event.type === "lesson_complete" ? 18 : event.type === "focus_complete" ? 12 : 8;
  const streakBonus = event.streakDay >= 7 ? 4 : event.streakDay >= 3 ? 2 : 0;
  const minuteBonus = Math.floor(event.baseMinutes / 25) * 0;

  return {
    stars: baseStars + streakBonus + minuteBonus,
    xp: baseStars * 4 + streakBonus * 2,
    rarityProgress: event.type === "lesson_complete" ? 0.18 : 0.08,
    message: event.type === "lesson_complete" ? "课时完成，知星和连续奖励一起到账。" : "学习反馈已到账。"
  };
}
```

Create `packages/reward-engine/src/index.ts`:

```ts
export * from "./rewardRules";
```

- [ ] **Step 2: Add avatar kit package**

Create `packages/avatar-kit/package.json`:

```json
{
  "name": "@zhiyao/avatar-kit",
  "version": "0.1.0",
  "private": true,
  "main": "src/index.ts",
  "scripts": {
    "test": "jest"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "ts-jest": "^29.2.5",
    "typescript": "^5.0.0"
  }
}
```

Create `packages/avatar-kit/src/avatarTypes.ts`:

```ts
export type EquipmentSlot = "material" | "accessory" | "aura" | "voice";

export type AvatarItem = {
  id: string;
  name: string;
  slot: EquipmentSlot;
  rarity: "common" | "rare" | "epic" | "legendary";
  price: number;
};

export type EquippedAvatar = Record<EquipmentSlot, string | null>;
```

Create `packages/avatar-kit/src/equipment.test.ts`:

```ts
import { equipItem } from "./equipment";

describe("avatar equipment", () => {
  it("equips an item into its matching slot", () => {
    const equipped = equipItem(
      { material: null, accessory: null, aura: null, voice: null },
      { id: "aura_sunrise", name: "晨光光环", slot: "aura", rarity: "rare", price: 80 }
    );

    expect(equipped).toEqual({ material: null, accessory: null, aura: "aura_sunrise", voice: null });
  });
});
```

Create `packages/avatar-kit/src/equipment.ts`:

```ts
import type { AvatarItem, EquippedAvatar } from "./avatarTypes";

export function equipItem(current: EquippedAvatar, item: AvatarItem): EquippedAvatar {
  return {
    ...current,
    [item.slot]: item.id
  };
}
```

Create `packages/avatar-kit/src/index.ts`:

```ts
export * from "./avatarTypes";
export * from "./equipment";
```

- [ ] **Step 3: Run package tests**

Run from `zhiyao-gamification-lab`:

```powershell
npm install
npm test
```

Expected: reward-engine and avatar-kit tests pass.

- [ ] **Step 4: Commit lab packages**

```powershell
git add packages package.json package-lock.json
git commit -m "feat: add gamification lab packages"
```

## Task 8: Build Gamification Lab Demo Screen

**Files:**
- Create: `zhiyao-gamification-lab/packages/ui-rewards/package.json`
- Create: `zhiyao-gamification-lab/packages/ui-rewards/src/index.ts`
- Create: `zhiyao-gamification-lab/packages/ui-rewards/src/RewardBurst.tsx`
- Create: `zhiyao-gamification-lab/packages/ui-rewards/src/ShopShelf.tsx`
- Create: `zhiyao-gamification-lab/apps/demo-expo/src/screens/LabHomeScreen.tsx`
- Modify: `zhiyao-gamification-lab/apps/demo-expo/app/index.tsx`

- [ ] **Step 1: Add UI rewards package**

Create `packages/ui-rewards/package.json`:

```json
{
  "name": "@zhiyao/ui-rewards",
  "version": "0.1.0",
  "private": true,
  "main": "src/index.ts",
  "peerDependencies": {
    "react": "*",
    "react-native": "*"
  }
}
```

Create `packages/ui-rewards/src/RewardBurst.tsx`:

```tsx
import { Text, View } from "react-native";

export function RewardBurst({ stars, message }: { stars: number; message: string }) {
  return (
    <View style={{ borderRadius: 24, padding: 16, backgroundColor: "#F6C453", alignItems: "center" }}>
      <Text style={{ fontSize: 24, fontWeight: "800", color: "#0F172A" }}>+{stars} 知星</Text>
      <Text style={{ marginTop: 6, color: "#334155" }}>{message}</Text>
    </View>
  );
}
```

Create `packages/ui-rewards/src/ShopShelf.tsx`:

```tsx
import { Text, View } from "react-native";

export type ShopItemView = {
  id: string;
  name: string;
  price: number;
  owned: boolean;
};

export function ShopShelf({ items }: { items: ShopItemView[] }) {
  return (
    <View style={{ gap: 10 }}>
      {items.map((item) => (
        <View key={item.id} style={{ borderRadius: 18, padding: 14, backgroundColor: "white", borderWidth: 1, borderColor: "#E2E8F0" }}>
          <Text style={{ fontWeight: "700", color: "#0F172A" }}>{item.name}</Text>
          <Text style={{ color: "#64748B" }}>{item.owned ? "已拥有" : `${item.price} 知星`}</Text>
        </View>
      ))}
    </View>
  );
}
```

Create `packages/ui-rewards/src/index.ts`:

```ts
export * from "./RewardBurst";
export * from "./ShopShelf";
```

- [ ] **Step 2: Add lab demo screen**

Create `apps/demo-expo/src/screens/LabHomeScreen.tsx`:

```tsx
import { useMemo, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { applyLearningEvent } from "../../../packages/reward-engine/src";
import { equipItem, type AvatarItem, type EquippedAvatar } from "../../../packages/avatar-kit/src";
import { RewardBurst, ShopShelf } from "../../../packages/ui-rewards/src";

const shopItems: AvatarItem[] = [
  { id: "aura_sunrise", name: "晨光光环", slot: "aura", rarity: "rare", price: 80 },
  { id: "pin_gold", name: "金色胸针", slot: "accessory", rarity: "common", price: 40 }
];

export function LabHomeScreen() {
  const [stars, setStars] = useState(120);
  const [lastReward, setLastReward] = useState(applyLearningEvent({ type: "lesson_complete", baseMinutes: 25, streakDay: 7 }));
  const [equipped, setEquipped] = useState<EquippedAvatar>({ material: null, accessory: null, aura: null, voice: null });

  const shelfItems = useMemo(() => shopItems.map((item) => ({ id: item.id, name: item.name, price: item.price, owned: Object.values(equipped).includes(item.id) })), [equipped]);

  return (
    <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 72, gap: 18, backgroundColor: "#F8FAFC" }}>
      <Text style={{ fontSize: 30, fontWeight: "800", color: "#0F172A" }}>Gamification Lab</Text>
      <Text style={{ color: "#64748B" }}>余额：{stars} 知星</Text>
      <RewardBurst stars={lastReward.stars} message={lastReward.message} />
      <Pressable
        style={{ minHeight: 52, borderRadius: 999, backgroundColor: "#35D3B4", alignItems: "center", justifyContent: "center" }}
        onPress={() => {
          const reward = applyLearningEvent({ type: "lesson_complete", baseMinutes: 25, streakDay: 7 });
          setLastReward(reward);
          setStars((value) => value + reward.stars);
        }}
      >
        <Text style={{ fontWeight: "800", color: "#0F172A" }}>模拟完成课时</Text>
      </Pressable>
      <ShopShelf items={shelfItems} />
      <Pressable
        style={{ minHeight: 52, borderRadius: 999, backgroundColor: "#0F172A", alignItems: "center", justifyContent: "center" }}
        onPress={() => {
          const item = shopItems[0];
          if (stars >= item.price) {
            setStars((value) => value - item.price);
            setEquipped((value) => equipItem(value, item));
          }
        }}
      >
        <Text style={{ fontWeight: "800", color: "white" }}>购买并装备晨光光环</Text>
      </Pressable>
      <View style={{ borderRadius: 24, padding: 16, backgroundColor: "white" }}>
        <Text style={{ color: "#0F172A", fontWeight: "800" }}>当前装备</Text>
        <Text style={{ marginTop: 8, color: "#64748B" }}>{JSON.stringify(equipped, null, 2)}</Text>
      </View>
    </ScrollView>
  );
}
```

Modify `apps/demo-expo/app/index.tsx`:

```tsx
import { LabHomeScreen } from "../src/screens/LabHomeScreen";
export default LabHomeScreen;
```

- [ ] **Step 3: Verify lab demo**

Run from `zhiyao-gamification-lab/apps/demo-expo`:

```powershell
npx expo start --clear
```

Expected: demo shows balance, reward burst, shop shelf, and equipment JSON. Tapping “模拟完成课时” increases stars. Tapping “购买并装备晨光光环” spends stars and equips aura.

- [ ] **Step 4: Commit lab demo**

```powershell
git add apps packages
git commit -m "feat: add gamification lab demo"
```

## Task 9: Phase 1 Verification And Handoff Notes

**Files:**
- Create: `zhiyao-mobile-app/docs/phase-1-verification.md`
- Create: `zhiyao-gamification-lab/docs/phase-1-verification.md`

- [ ] **Step 1: Verify main app tests**

Run from `zhiyao-mobile-app`:

```powershell
npm test
```

Expected: all Jest tests pass.

- [ ] **Step 2: Verify main app manual flow**

Run:

```powershell
npx expo start --clear
```

Manual expected flow:

```txt
首页 opens with low-poly Agent.
Tap 开始今日学习.
学习 tab opens.
Tap 函数的概念.
StudySpace shell opens.
Tap 完成课时.
Reward toast appears with +18 知星 and next lesson unlock text.
Open 我的 tab.
Balance and equipped starter assets are visible.
```

- [ ] **Step 3: Verify lab tests and demo**

Run from `zhiyao-gamification-lab`:

```powershell
npm test
npm run demo
```

Expected: package tests pass and the Expo demo starts.

- [ ] **Step 4: Document verification results**

Create `zhiyao-mobile-app/docs/phase-1-verification.md`:

```md
# Phase 1 Verification

## Automated

- `npm test`: pass

## Manual

- Home Agent hub visible.
- Home primary action opens Learn.
- Learn course item opens StudySpace.
- StudySpace completion shows Agent celebration and `+18 知星`.
- Profile shows balance and starter equipment state.

## Remaining Product Work

- Replace simplified low-poly placeholder with production avatar assets.
- Replace sample lessons with `/curriculum` and `/studyspace` API data.
- Connect reward toast to `/stars` and `/cosmetics` once API sessions are active.
```

Create `zhiyao-gamification-lab/docs/phase-1-verification.md`:

```md
# Phase 1 Verification

## Automated

- `npm test`: pass

## Manual

- Demo app starts.
- Simulated lesson completion increases stars.
- Shop shelf displays item price and owned state.
- Purchase action spends stars and equips aura.

## Promotion Candidates

- `reward-engine` event and reward result types.
- `avatar-kit` equipment slot model.
- `ui-rewards` reward burst and shop shelf interaction patterns.
```

- [ ] **Step 5: Commit verification docs**

```powershell
git add docs
git commit -m "docs: record phase 1 verification"
```

## Self-Review

- Spec coverage: Main Expo app, 4 Tab IA, Agent-first home, StudySpace shell, Focus entry placement, reward feedback, Profile asset display, Gamification Lab packages, shop/equipment loop, and verification are covered.
- Placeholder scan: This plan avoids red-flag placeholder wording, unspecified handlers, and vague test instructions.
- Type consistency: Agent mood/equipment, StudySpace completion, reward classification, and lab equipment slots use consistent names across tasks.
