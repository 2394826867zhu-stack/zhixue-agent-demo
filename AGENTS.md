<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## UI/UX Iteration Workflow

For UI/UX redesign, motion, navigation, visual polish, or interaction-quality requests:

1. Do not change UI code immediately unless the user explicitly asks to implement at once.
2. First inspect the current UI structure and relevant files, then provide an autonomous review report.
3. Provide a concrete design方案 with visual direction, component behavior, motion rules, affected files, risks, and acceptance criteria.
4. Discuss the plan with the user and wait for explicit confirmation before modifying files.
5. After implementation, verify in the browser and report what changed plus any remaining risks.
