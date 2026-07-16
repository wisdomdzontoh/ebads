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
 * expo-background-task is native-only; the `.web` sibling is a no-op so the web build works.
 */

import * as BackgroundTask from 'expo-background-task';
import * as TaskManager from 'expo-task-manager';

import { ApiClient } from './api';
import { runSync } from './sync';

export const BACKGROUND_SYNC_TASK = 'ebads-background-sync';

// Defined once, at module load, so TaskManager can resolve it when the OS wakes the app.
// The base URL / key are read fresh from storage each run (the task has no React context).
TaskManager.defineTask(BACKGROUND_SYNC_TASK, async () => {
  try {
    const { getItem } = await import('./storage');
    const stored = await getItem('settings');
    const settings = stored ? (JSON.parse(stored) as { baseUrl?: string; apiKey?: string }) : {};
    if (!settings.baseUrl) return BackgroundTask.BackgroundTaskResult.Success;
    const api = new ApiClient({ baseUrl: settings.baseUrl, apiKey: settings.apiKey || undefined });
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
