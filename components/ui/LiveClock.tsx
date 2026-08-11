"use client";

import { useEffect, useState } from "react";

export function LiveClock({ className }: { className?: string }) {
  const [now, setNow] = useState<string | null>(null);
  useEffect(() => {
    const update = () => {
      const d = new Date();
      const t = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
      setNow(t);
    };
    update();
    const i = setInterval(update, 1000);
    return () => clearInterval(i);
  }, []);
  return (
    <span className={`font-mono text-xs tabular-nums tracking-wider text-ink-200 ${className ?? ""}`}>
      {now ?? "--:--:--"}
    </span>
  );
}
