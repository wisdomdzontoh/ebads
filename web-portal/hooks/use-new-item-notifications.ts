"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Fires a browser (OS-level) Notification for every item that's newly present since the last
 * call — the web portal's answer to "facility staff get no live alert when a reservation
 * arrives" (there is no push/WebSocket channel in this architecture, docs/01 §3.6 — SMS/push
 * gateways are log-only server-side too). Pairs with a polling `useQuery` (the existing
 * REFRESH_INTERVAL_MS on the Incoming allocations page): each successful poll re-runs this
 * hook with the latest list, and any id not seen on a PRIOR call gets a Notification — so the
 * facility doesn't have to keep the tab focused and watch the list to notice something new.
 *
 * The FIRST call (nothing seen yet) seeds the "already known" set without notifying — arriving
 * on the page shouldn't re-notify for everything already sitting there.
 */
export function useNewItemNotifications<T>(
  items: T[] | undefined,
  getId: (item: T) => string,
  describe: (item: T) => { title: string; body: string },
): { permission: NotificationPermission | "unsupported"; requestPermission: () => void } {
  const seenRef = useRef<Set<string> | null>(null);
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(
    "unsupported",
  );

  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) return;
    // One-time sync from the browser's own permission state (an external system) at mount —
    // same justified exception as components/auth-provider.tsx's cookie hydration.
    /* eslint-disable-next-line react-hooks/set-state-in-effect */
    setPermission(Notification.permission);
  }, []);

  const requestPermission = () => {
    if (typeof window === "undefined" || !("Notification" in window)) return;
    void Notification.requestPermission().then(setPermission);
  };

  useEffect(() => {
    if (!items) return;
    const currentIds = new Set(items.map(getId));

    if (seenRef.current === null) {
      // First observation — nothing to notify about yet, just establish the baseline.
      seenRef.current = currentIds;
      return;
    }

    const canNotify =
      typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted";

    for (const item of items) {
      const id = getId(item);
      if (seenRef.current.has(id)) continue;
      if (canNotify) {
        const { title, body } = describe(item);
        const notification = new Notification(title, { body, tag: id });
        notification.onclick = () => {
          window.focus();
          notification.close();
        };
      }
    }

    seenRef.current = currentIds;
    // `getId`/`describe` are expected to be stable per call site (defined inline is fine —
    // they're only read, never depended on for the diff itself, which is keyed by `items`).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items]);

  return { permission, requestPermission };
}
