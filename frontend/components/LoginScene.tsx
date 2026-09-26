"use client";

function RotatingCube() {
  return (
    <div className="relative h-32 w-32 animate-rotate-y" aria-hidden>
      {[0, 1, 2, 3, 4, 5].map((i) => {
        const faces = [
          { transform: "translateZ(60px)" },
          { transform: "rotateY(90deg) translateZ(60px)" },
          { transform: "rotateY(180deg) translateZ(60px)" },
          { transform: "rotateY(270deg) translateZ(60px)" },
          { transform: "rotateX(90deg) translateZ(60px)" },
          { transform: "rotateX(-90deg) translateZ(60px)" },
        ];
        return (
          <div
            key={i}
            className="absolute inset-0 rounded-2xl border border-white/25 bg-gradient-to-br from-brand-500/40 to-brand-700/40 backdrop-blur-sm"
            style={faces[i]}
          />
        );
      })}
    </div>
  );
}

function OrbitingRing() {
  return (
    <div className="relative h-40 w-40 animate-rotate-x" aria-hidden>
      <span className="absolute inset-0 rounded-full border border-brand-300/40" />
      <span className="absolute inset-4 rounded-full border border-brand-400/30" />
      <span className="absolute inset-8 rounded-full border border-brand-300/25" />
      <span className="absolute left-1/2 top-0 h-3 w-3 -translate-x-1/2 rounded-full bg-brand-200 shadow-[0_0_14px_rgba(164,189,166,0.9)]" />
      <span className="absolute bottom-0 left-1/2 h-2 w-2 -translate-x-1/2 rounded-full bg-brand-300/80" />
    </div>
  );
}

function Mountains() {
  return (
    <svg className="absolute bottom-0 left-0 h-48 w-full" viewBox="0 0 800 200" preserveAspectRatio="none" aria-hidden>
      <path d="M0 200 V120 L120 40 L240 150 L360 60 L520 170 L680 90 L800 160 V200 Z" fill="#ffffff" opacity="0.05" />
      <path d="M0 200 V150 L140 90 L300 180 L460 110 L620 190 L780 140 L800 150 V200 Z" fill="#ffffff" opacity="0.035" />
    </svg>
  );
}

export default function LoginScene() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <div
        className="scene-3d absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
        style={{ animationDuration: "16s" }}
      >
        <div className="animate-float-3d">
          <RotatingCube />
        </div>
      </div>

      <div className="sidebar-grid absolute inset-0 opacity-60" />

      <div className="scene-3d animate-breathe absolute -right-10 top-16" style={{ animationDuration: "20s" }}>
        <RotatingCube />
      </div>

      <div
        className="scene-3d animate-tilt absolute bottom-14 left-10"
        style={{
          background: "radial-gradient(circle at 30% 30%, rgba(255,255,255,0.9), rgba(255,255,255,0.55) 55%, transparent 70%)",
          boxShadow: "0 20px 50px rgba(0,0,0,0.25)",
        }}
      >
        <OrbitingRing />
      </div>

      <Mountains />
    </div>
  );
}