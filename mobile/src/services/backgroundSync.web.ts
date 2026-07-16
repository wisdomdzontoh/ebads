/**
 * Background sync (web no-op). expo-background-task is native-only; on web the foreground
 * interval in SyncContext handles refresh, so registration does nothing here.
 */

export const BACKGROUND_SYNC_TASK = 'ebads-background-sync';

export async function registerBackgroundSync(_intervalMinutes: number): Promise<void> {
  // No background tasks on web; foreground interval sync covers it.
}
