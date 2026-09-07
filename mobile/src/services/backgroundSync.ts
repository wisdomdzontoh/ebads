/**
 * Background facility sync (docs/05 §5).
 *
 * Registers a background task that refreshes the facility cache on the OS's schedule (the
 * requested `minimumInterval` mirrors the configured sync interval; the OS may run it less
 * often). The task is defined at module scope — a hard requirement of expo-task-manager, which
 * must find the task by name when the app is woken in the background. It reuses the same
 * best-effort `runSync` as the foreground triggers, so a background failure leaves a stale
 * timestamp rather than a silent success (docs/05 §5).
 *
 * Auth (EBADS_PRD.md §10): `GET /facilities` requires a bearer token now (Increment 1). The
 * task has no React context, so it reads the session straight from `secureStorage` — same
 * session `state/AuthContext.tsx` reads/writes — and refreshes the access token itself on a
 * 401, persisting the new one so the next run (and the next foreground launch) picks it up. No
 * session at all (never signed in, or signed out) is a normal, silent no-op, not a failure.
 * The engine URL is the same build-time `ENGINE_BASE_URL` constant every other client uses
 * (services/env.ts) — nothing to read from settings storage for that half anymore.
 *
 * expo-background-task is native-only; the `.web` sibling is a no-op so the web build works.
 */

import * as BackgroundTask from 'expo-background-task';
import * as TaskManager from 'expo-task-manager';

import { ApiClient } from './api';
import { readSession, storeRefreshedAccessToken } from './auth';
import { ENGINE_BASE_URL } from './env';
import { runSync } from './sync';

export const BACKGROUND_SYNC_TASK = 'ebads-background-sync';

// Defined once, at module load, so TaskManager can resolve it when the OS wakes the app.
// The session is read fresh from storage each run (the task has no React context).
TaskManager.defineTask(BACKGROUND_SYNC_TASK, async () => {
  try {
    const session = await readSession();
    if (!session) return BackgroundTask.BackgroundTaskResult.Success;

    let current = session;
    const api: ApiClient = new ApiClient({
      baseUrl: ENGINE_BASE_URL,
      getAccessToken: () => current.accessToken,
      onUnauthorized: async (): Promise<string | null> => {
        try {
          const { access_token: accessToken } = await api.refreshAccessToken(current.refreshToken);
          current = await storeRefreshedAccessToken(current, accessToken);
          return accessToken;
        } catch {
          return null; // refresh token itself is dead — next foreground launch signs out
        }
      },
    });

    const outcome = await runSync(api);
    return outcome.ok
      ? BackgroundTask.BackgroundTaskResult.Success
      : BackgroundTask.BackgroundTaskResult.Failed;
  } catch {
    return BackgroundTask.BackgroundTaskResult.Failed;
  }
});

/** Register (or re-register) the background sync task at the given interval, in minutes. */
export async function registerBackgroundSync(intervalMinutes: number): Promise<void> {
  try {
    await BackgroundTask.registerTaskAsync(BACKGROUND_SYNC_TASK, {
      minimumInterval: Math.max(1, intervalMinutes),
    });
  } catch {
    // Registration can fail on unsupported platforms/emulators — foreground sync still works.
  }
}
