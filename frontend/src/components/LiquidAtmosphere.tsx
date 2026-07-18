import { useReducedMotion } from "motion/react"

type LiquidAtmosphereProps = {
  intensity?: "gate" | "workspace"
}

export function LiquidAtmosphere({ intensity = "gate" }: LiquidAtmosphereProps) {
  const reducedMotion = useReducedMotion()
  const animate = !reducedMotion

  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden"
      aria-hidden="true"
    >
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,oklch(0.2_0.04_170/0.35),transparent_55%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,oklch(0.18_0.03_170/0.28),transparent_50%)]" />

      <svg
        className={`absolute ${intensity === "gate" ? "-left-[12%] top-[8%] h-[70%] w-[48%]" : "-left-[18%] bottom-[-10%] h-[55%] w-[42%] opacity-40"}`}
        viewBox="0 0 600 800"
        fill="none"
      >
        <defs>
          <linearGradient id="liquid-a" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="oklch(0.72 0.04 170)" stopOpacity="0.55" />
            <stop offset="55%" stopColor="oklch(0.52 0.08 170)" stopOpacity="0.28" />
            <stop offset="100%" stopColor="oklch(0.3 0.04 170)" stopOpacity="0.05" />
          </linearGradient>
          <filter id="soft-blur">
            <feGaussianBlur stdDeviation="8" />
          </filter>
        </defs>
        <path
          d="M120 40 C220 120 80 220 180 320 C280 420 90 500 160 620 C210 700 320 740 380 780"
          stroke="url(#liquid-a)"
          strokeWidth="54"
          strokeLinecap="round"
          filter="url(#soft-blur)"
          className={animate ? "origin-center animate-[liquid-drift_18s_ease-in-out_infinite_alternate]" : undefined}
        />
        <path
          d="M70 120 C170 180 40 280 140 380 C240 480 60 560 130 680"
          stroke="oklch(0.86 0.01 170 / 0.18)"
          strokeWidth="18"
          strokeLinecap="round"
          className={animate ? "origin-center animate-[liquid-drift_22s_ease-in-out_infinite_alternate-reverse]" : undefined}
        />
      </svg>

      <svg
        className={`absolute ${intensity === "gate" ? "-right-[10%] bottom-[4%] h-[65%] w-[46%]" : "-right-[14%] top-[-8%] h-[48%] w-[36%] opacity-35"}`}
        viewBox="0 0 600 800"
        fill="none"
      >
        <defs>
          <linearGradient id="liquid-b" x1="1" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="oklch(0.8 0.02 170)" stopOpacity="0.4" />
            <stop offset="60%" stopColor="oklch(0.48 0.07 170)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="oklch(0.25 0.03 170)" stopOpacity="0.04" />
          </linearGradient>
        </defs>
        <path
          d="M480 60 C360 140 520 240 400 340 C280 440 500 520 390 640 C320 720 220 760 160 790"
          stroke="url(#liquid-b)"
          strokeWidth="48"
          strokeLinecap="round"
          filter="url(#soft-blur)"
          className={animate ? "origin-center animate-[liquid-drift_20s_ease-in-out_infinite_alternate]" : undefined}
        />
      </svg>

      <style>{`
        @keyframes liquid-drift {
          0% { transform: translate3d(0, 0, 0) scale(1); opacity: 0.9; }
          100% { transform: translate3d(12px, -18px, 0) scale(1.04); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
