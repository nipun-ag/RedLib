import { useEffect, useState } from "react";
import { formatNumber } from "../lib/utils";

export default function CountUpNumber({ value, duration = 1000 }) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    let animationFrameId = 0;
    let startTime = 0;

    function tick(timestamp) {
      if (!startTime) {
        startTime = timestamp;
      }

      const progress = Math.min((timestamp - startTime) / duration, 1);
      const eased = 1 - (1 - progress) ** 3;
      setDisplayValue(Math.round(value * eased));

      if (progress < 1) {
        animationFrameId = window.requestAnimationFrame(tick);
      }
    }

    setDisplayValue(0);
    animationFrameId = window.requestAnimationFrame(tick);

    return () => {
      window.cancelAnimationFrame(animationFrameId);
    };
  }, [duration, value]);

  return <>{formatNumber(displayValue)}</>;
}
