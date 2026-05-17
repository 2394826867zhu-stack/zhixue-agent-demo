/**
 * 知曜四叶涡轮标志 — 实心填充版
 *
 * 构造原理（对照 zhiyaoui001.png 线稿）：
 *   每片叶片 = 大弧（外凸，顺时针）+ 小弧（内凹，逆时针）围成封闭实心区域
 *   4 片叶片各旋转 90°，形成涡轮旋转感
 *   fill="currentColor" → 自动继承父级主色，无需任何 filter
 */
export function TurbineLogo({ className }: { className?: string }) {
  /**
   * 单片叶片路径（东北象限，12点→3点位置）：
   *   M 12 2          从 12点位出发
   *   A 12 12 0 0 1 22 12   外凸大弧顺时针扫到 3点位（r=12）
   *   A 8  8  0 0 0 12 2    内凹小弧逆时针返回起点（r=8）
   *   Z               闭合
   */
  const blade = "M12 2 A12 12 0 0 1 22 12 A8 8 0 0 0 12 2Z";

  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <path d={blade} />
      <path d={blade} transform="rotate(90 12 12)" />
      <path d={blade} transform="rotate(180 12 12)" />
      <path d={blade} transform="rotate(270 12 12)" />
    </svg>
  );
}
