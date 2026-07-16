/**
 * Connectivity state — the online/offline signal the whole app switches on (docs/05 §3).
 *
 * Subscribes once to connectivity changes and exposes the current status. The Dispatch screen
 * enables submission only when online; every screen shows the offline banner when not. This is
 * the single gate behind the strict offline boundary (no matching, no requests when offline).
 */

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { checkOnline, subscribeConnectivity } from '../services/connectivity';

interface ConnectivityContextValue {
  online: boolean;
}

const ConnectivityContext = createContext<ConnectivityContextValue>({ online: true });

export function ConnectivityProvider({
  children,
}: {
  children: React.ReactNode;
}): React.ReactElement {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let active = true;
    void checkOnline().then((value) => {
      if (active) setOnline(value);
    });
    const unsubscribe = subscribeConnectivity((value) => {
      if (active) setOnline(value);
    });
    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  const value = useMemo(() => ({ online }), [online]);
  return <ConnectivityContext.Provider value={value}>{children}</ConnectivityContext.Provider>;
}

/** Read the current online/offline status. */
export function useConnectivity(): ConnectivityContextValue {
  return useContext(ConnectivityContext);
}
