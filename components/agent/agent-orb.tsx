"use client";

import { cn } from "@/lib/utils";

const TURBINE_PATH =
  "M9.149 23.812 C7.148 23.448 5.383 20.951 6.655 20.284 C6.857 20.178 6.986 20.17 9.068 20.138 C11.773 20.096 12.274 20.012 13.257 19.435 C13.685 19.184 14.389 18.608 14.362 18.53 C14.349 18.493 14.356 18.468 14.378 18.474 C14.433 18.489 14.661 18.335 14.661 18.282 C14.661 18.258 14.63 18.255 14.593 18.276 C14.555 18.298 14.609 18.226 14.712 18.117 C14.897 17.921 15.009 17.842 14.878 18 C14.841 18.045 14.832 18.081 14.858 18.081 C14.954 18.081 16.476 16.437 17.389 15.346 C17.799 14.856 17.96 14.746 18.191 14.797 C18.678 14.904 18.751 15.177 18.724 16.805 C18.699 18.306 18.643 18.493 17.812 19.857 C15.412 23.795 15.257 23.894 11.511 23.886 C10.156 23.883 9.409 23.86 9.149 23.812 Z M5.881 18.682 C5.058 18.551 4.235 18.17 2.932 17.315 C1.078 16.097 0.415 15.321 0.267 14.196 C0.168 13.446 0.231 9.496 0.348 9.098 C0.903 7.211 3.438 5.332 4.031 6.369 C4.083 6.459 4.107 7.209 4.132 9.394 C4.168 12.689 4.167 12.683 4.64 13.623 C5.037 14.412 6.287 15.882 6.466 15.771 C6.507 15.746 6.519 15.752 6.497 15.787 C6.451 15.862 6.822 16.193 7.749 16.902 C8.161 17.218 8.54 17.548 8.593 17.638 C8.819 18.024 8.601 18.49 8.131 18.622 C7.85 18.701 6.27 18.743 5.881 18.682 Z M6.186 8.132 C5.858 8.001 5.785 7.775 5.765 6.839 C5.734 5.41 5.874 4.938 6.776 3.419 C8.053 1.269 8.573 0.692 9.6 0.282 L9.964 0.137 L12.592 0.12 C14.86 0.104 15.279 0.114 15.659 0.191 C17.238 0.51 18.507 2.367 17.742 3.238 C17.415 3.61 17.446 3.606 14.824 3.641 C10.944 3.694 9.997 4.159 7.575 7.206 C6.775 8.212 6.63 8.309 6.186 8.132 Z M20.663 17.138 C20.433 16.909 20.417 16.715 20.417 14.203 C20.416 11.157 20.351 10.775 19.64 9.676 C19.205 9.004 17.396 7.222 16.464 6.548 C15.517 5.864 15.764 5.2 16.995 5.121 C18.402 5.03 19.425 5.289 20.552 6.021 C22.237 7.114 23.019 7.793 23.363 8.461 C23.703 9.12 23.701 9.106 23.701 12 L23.701 14.633 L23.551 15.04 C23.053 16.386 21.233 17.708 20.663 17.138 Z M11.259 14.333 C10.24 14.131 9.339 13.023 9.339 11.97 C9.339 9.713 12.02 8.626 13.608 10.237 C15.344 11.999 13.726 14.821 11.259 14.333 Z";

function DetailedMark({ thinking, pressed }: { thinking?: boolean; pressed?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-full w-full overflow-visible">
      <defs>
        <radialGradient id="agent-core" cx="42%" cy="34%" r="68%">
          <stop offset="0%" stopColor="oklch(0.92 0.10 170)" />
          <stop offset="42%" stopColor="oklch(0.70 0.16 170)" />
          <stop offset="100%" stopColor="oklch(0.42 0.12 190)" />
        </radialGradient>
        <linearGradient id="agent-edge" x1="4" x2="20" y1="3" y2="21">
          <stop offset="0%" stopColor="oklch(0.98 0.07 170 / 0.92)" />
          <stop offset="38%" stopColor="oklch(0.76 0.17 170 / 0.86)" />
          <stop offset="100%" stopColor="oklch(0.36 0.11 205 / 0.82)" />
        </linearGradient>
        <linearGradient id="agent-flow" x1="0" x2="24" y1="4" y2="20">
          <stop offset="0%" stopColor="oklch(1 0 0 / 0)" />
          <stop offset="42%" stopColor="oklch(0.92 0.12 170 / 0.72)" />
          <stop offset="100%" stopColor="oklch(1 0 0 / 0)" />
        </linearGradient>
        <filter id="agent-shadow" x="-45%" y="-45%" width="190%" height="190%">
          <feDropShadow dx="0" dy="1.2" stdDeviation="1.1" floodColor="oklch(0.12 0.03 230)" floodOpacity="0.24" />
          <feDropShadow dx="0" dy="0" stdDeviation="1.9" floodColor="oklch(0.64 0.17 170)" floodOpacity="0.48" />
        </filter>
      </defs>
      <g
        className={cn(
          "origin-center transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
          thinking && "animate-agent-rotate",
          pressed && "animate-agent-kick"
        )}
        filter="url(#agent-shadow)"
      >
        <path d={TURBINE_PATH} fill="url(#agent-core)" />
        <path d={TURBINE_PATH} fill="none" stroke="url(#agent-edge)" strokeWidth="0.28" opacity="0.72" />
        <path d={TURBINE_PATH} fill="oklch(1 0 0 / 0.22)" transform="translate(-0.35 -0.42) scale(0.992 0.992)" />
        <path d={TURBINE_PATH} fill="url(#agent-flow)" className="animate-agent-surface-flow" opacity="0.42" />
      </g>
      <circle cx="12" cy="12" r="1.78" fill="oklch(0.98 0.035 170)" />
      <circle cx="12" cy="12" r="1.16" fill="oklch(0.50 0.14 180)" className={cn(thinking && "animate-agent-core")} />
    </svg>
  );
}

export function AgentOrb({
  active,
  thinking,
  pressed,
  className,
}: {
  active?: boolean;
  thinking?: boolean;
  pressed?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "group/orb relative grid place-items-center",
        active && "is-active",
        thinking && "is-thinking",
        className
      )}
    >
      <div className="absolute inset-[-34%] rounded-full bg-primary/24 blur-xl opacity-70 transition-opacity duration-300 group-hover/orb:opacity-100" />
      <div
        className={cn(
          "relative grid h-full w-full place-items-center text-primary transition duration-300 group-hover/orb:scale-[1.06]",
          pressed && "scale-95"
        )}
      >
        <DetailedMark thinking={thinking} pressed={pressed} />
      </div>
    </div>
  );
}
