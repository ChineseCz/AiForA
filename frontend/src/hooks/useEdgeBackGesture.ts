import { useEffect } from "react";
import { App as CapacitorApp } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

type EdgeBackOptions = {
  enabled: boolean;
  onBack: () => boolean;
};

const EDGE_WIDTH = 32;
const BACK_DISTANCE = 84;
const MAX_VERTICAL_DISTANCE = 72;

/** Android-style back gesture: drag from the right screen edge toward the left. */
export function useEdgeBackGesture({ enabled, onBack }: EdgeBackOptions) {
  useEffect(() => {
    if (!enabled) return;

    let startX = 0;
    let startY = 0;
    let tracking = false;

    const onTouchStart = (event: TouchEvent) => {
      if (event.touches.length !== 1) return;
      const touch = event.touches[0];
      tracking = touch.clientX >= window.innerWidth - EDGE_WIDTH;
      startX = touch.clientX;
      startY = touch.clientY;
    };

    const onTouchEnd = (event: TouchEvent) => {
      if (!tracking || event.changedTouches.length !== 1) return;
      tracking = false;
      const touch = event.changedTouches[0];
      const horizontalDistance = startX - touch.clientX;
      const verticalDistance = Math.abs(startY - touch.clientY);
      if (horizontalDistance >= BACK_DISTANCE && verticalDistance <= MAX_VERTICAL_DISTANCE) onBack();
    };

    const cancel = () => { tracking = false; };
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchend", onTouchEnd, { passive: true });
    window.addEventListener("touchcancel", cancel, { passive: true });
    return () => {
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchend", onTouchEnd);
      window.removeEventListener("touchcancel", cancel);
    };
  }, [enabled, onBack]);

  useEffect(() => {
    if (!enabled || !Capacitor.isNativePlatform()) return;

    let removed = false;
    let removeListener: (() => Promise<void>) | undefined;
    CapacitorApp.addListener("backButton", () => {
      onBack();
    }).then((handle) => {
      if (removed) handle.remove();
      else removeListener = handle.remove;
    });

    return () => {
      removed = true;
      void removeListener?.();
    };
  }, [enabled, onBack]);
}
