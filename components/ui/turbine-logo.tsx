/**
 * 知曜涡轮标志
 * 直接使用品牌原图 /public/logo.png（zhiyaoui001.png）
 * filter + mix-blend-mode 适配深色/浅色背景，形状完全还原
 */
import React from "react";

interface TurbineLogoProps {
  className?: string;
  /** dark=true 用于深色侧边栏（filter+screen混合），false 用于浅色背景 */
  dark?: boolean;
  /** 覆盖内联 style，用于精确控制滤镜颜色 */
  style?: React.CSSProperties;
}

export function TurbineLogo({ className, dark = false, style }: TurbineLogoProps) {
  const darkStyle: React.CSSProperties = {
    // 深色背景：先 invert 让线条变白，再 sepia+hue-rotate 着色为主色，screen 混合让背景消失
    filter: "invert(1) sepia(1) saturate(5) hue-rotate(138deg) brightness(0.9)",
    mixBlendMode: "screen",
    ...style,
  };

  const lightStyle: React.CSSProperties = {
    // 浅色背景：直接显示黑色线条原图，无需处理
    opacity: 0.85,
    ...style,
  };

  return (
    <img
      src="/logo.png"
      alt=""
      aria-hidden="true"
      className={className}
      style={dark ? darkStyle : lightStyle}
    />
  );
}
