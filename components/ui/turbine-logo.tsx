/**
 * 知曜四叶涡轮标志
 * 形状严格还原品牌 PNG：4 片弯刀形叶片，每片旋转 90° 组成涡轮
 * 使用 currentColor 继承父级颜色，尺寸由 className 控制
 */
export function TurbineLogo({ className }: { className?: string }) {
  // 单片叶片：从 12 点位到 3 点位的月牙弧面（外大弧 + 内小弧）
  const blade = "M12 7 A9 9 0 0 1 19 12 A5 5 0 0 0 12 7Z";

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
