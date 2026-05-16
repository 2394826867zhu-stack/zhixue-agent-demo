/**
 * 知曜品牌螺旋标志 — 两弧 + 中心点，呼应 SRS 循环生长意象
 * 不含颜色，外部通过 className / style 注入
 */
export function SpiralLogo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="知曜 logo"
    >
      {/* 外弧：从12点顺时针270°扫到9点位 */}
      <path
        d="M12 3A9 9 0 1 1 3 12"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      {/* 内弧：从9点位经上半圆逆时针至3点位（半圆，内径5.5） */}
      <path
        d="M6.5 12A5.5 5.5 0 0 0 17.5 12"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      {/* 中心点 */}
      <circle cx="12" cy="12" r="1.8" fill="currentColor" />
    </svg>
  );
}
