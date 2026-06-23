// 本地一次性渲染自检（非 CI）：用 Playwright 加载 admin 单页，stub /admin/* 响应，
// 驱动 登录→总览→反馈→客服，断言 DOM 真渲染（验证内嵌 JS 在真实浏览器跑通）。
// 跑法：node ../zhiyao-backend/app/admin_ui/_render_check.mjs（playwright 取自 mobile-app）
//   或 PW_NODE_MODULES=<含 playwright 的目录> node _render_check.mjs
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const here = dirname(fileURLToPath(import.meta.url));
const HTML = readFileSync(join(here, 'index.html'), 'utf8');
// playwright 装在 zhiyao-mobile-app；从那里解析（兼容从任意 cwd 运行）
const pwBase = process.env.PW_NODE_MODULES
  || join(here, '..', '..', '..', 'zhiyao-mobile-app') + '/';
const { chromium } = createRequire(pwBase)('playwright');

const env = (code, data) => ({ code, message: 'ok', data });
const ROUTES = {
  'POST /admin/auth/login': env(200, { access_token: 'tok', admin_id: 'a1', role: 'super_admin' }),
  'GET /admin/inbox-summary': env(200, {
    unresolved_feedback: 3, open_support_threads: 2, unresolved_dead_letters: 1,
    global_token_used_today: 1800000, global_token_limit: 5000000,
  }),
  'GET /admin/dashboard': env(200, {
    total_users: 42, active_users_today: 7, active_users_7d: 20, total_notes: 130,
    total_tokens_today: 120000, total_tokens_7d: 800000, total_cost_today_usd: 1.23,
    total_cost_7d_usd: 8.9, top_token_users: [], total_projects: 5, active_projects: 3,
    total_immersion_sessions: 0, total_focus_minutes: 0, total_ss_timeline_nodes: 0,
  }),
  'GET /admin/tokens/stats': env(200, {
    total_calls: 100, total_tokens: 800000, total_cost_usd: 8.9,
    by_model: [{ model: 'deepseek-v4-flash', total_tokens: 800000, cost_usd: 8.9 }],
    by_day: [{ date: '2026-06-17', cost_usd: 1.1 }, { date: '2026-06-18', cost_usd: 1.4 },
             { date: '2026-06-19', cost_usd: 0.9 }, { date: '2026-06-20', cost_usd: 1.8 },
             { date: '2026-06-21', cost_usd: 1.2 }, { date: '2026-06-22', cost_usd: 1.0 },
             { date: '2026-06-23', cost_usd: 1.5 }],
    top_users: [{ email: 'u@z.ai', user_id: 'u1', total_tokens: 50000 }],
  }),
  'GET /admin/feedback': env(200, { items: [
    { id: 'f1', category: 'bug', content: '崩溃了', status: 'open', created_at: '2026-06-23T10:00', admin_note: '', app_version: '1.0.0' },
  ], total: 1, page: 1, page_size: 20 }),
  'GET /admin/support/threads': env(200, { items: [
    { id: 't1', subject: '登录问题', status: 'open', last_message_at: '2026-06-23T09:00' },
  ], total: 1, page: 1, page_size: 20 }),
};

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error') errors.push('console.error: ' + m.text()); });

await page.route('**/admin/**', (route) => {
  const req = route.request();
  const url = new URL(req.url());
  const key = `${req.method()} ${url.pathname}`;
  const match = ROUTES[key] || Object.entries(ROUTES).find(([k]) => k === `${req.method()} ${url.pathname}`)?.[1];
  if (match) return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(match) });
  return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify(env(404, {})) });
});

const fail = (m) => { console.error('✗ ' + m); process.exitCode = 1; };
// 页面与 API 同源 http（file:// 下 fetch 会被 Chromium 拦）：/admin/ui 回 HTML，其余回 stub
await page.route('**/admin/ui', (route) =>
  route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: HTML }));
await page.goto('http://admin.local/admin/ui');

// 登录
await page.fill('#login-email', 'admin@zhiyao.com');
await page.fill('#login-pw', 'pw');
await page.click('#login-btn');
await page.waitForSelector('#shell:not(.hidden)', { timeout: 5000 }).catch(() => fail('登录后未进入主体'));

// 总览渲染：KPI + 成本图 + 全局闸
await page.waitForSelector('#view-dashboard .kpi', { timeout: 5000 }).catch(() => fail('总览 KPI 未渲染'));
const hasChart = await page.locator('#view-dashboard svg rect').count();
if (hasChart < 7) fail(`成本趋势柱图缺失（rect=${hasChart}）`);
const badge = await page.textContent('#b-feedback').catch(() => null);
if (badge !== '3') fail(`反馈徽章应为 3，实为 ${badge}`);

// 反馈视图
await page.click('nav button[data-view="feedback"]');
await page.waitForSelector('#view-feedback .card', { timeout: 5000 }).catch(() => fail('反馈卡片未渲染'));
if (!(await page.locator('text=崩溃了').count())) fail('反馈内容未渲染');

// 客服视图 → 工单行
await page.click('nav button[data-view="support"]');
await page.waitForSelector('#view-support table', { timeout: 5000 }).catch(() => fail('客服表格未渲染'));
if (!(await page.locator('text=登录问题').count())) fail('工单主题未渲染');

if (errors.length) fail('页面有 JS 错误:\n  ' + errors.join('\n  '));
if (!process.exitCode) console.log('✓ admin 单页真实浏览器渲染通过（登录→总览→反馈→客服，无 JS 错误）');
await browser.close();
