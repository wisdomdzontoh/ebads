/**
 * Notifications service (docs/05 §6).
 *
 * Thin wrapper over expo-notifications for the in-app recommendation alerts. The app requests
 * permission (during onboarding or from Settings) and can post a local notification when a
 * recommendation returns. The SMS path (Africa's Talking) is server-side and stubbed — the app
 * does not implement SMS (docs/05 §6). Push registration is best-effort: a denied permission
 * simply means no notifications, never a crash.
 */

import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import {
  recordNotification,
  type NotificationKind,
  type NotificationTarget,
} from './notificationHistory';

// Without a handler, Expo suppresses notifications while the app is foregrounded — which is
// exactly when a dispatch recommendation arrives. Registered once at module load.
try {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
} catch {
  // Unavailable platform (e.g. some web browsers) — notifications stay best-effort.
}

// Android 8+ delivers notifications through channels; create the app's channel up front so
// the first recommendation alert is not dropped or downgraded.
if (Platform.OS === 'android') {
  void Notifications.setNotificationChannelAsync('default', {
    name: 'Dispatch recommendations',
    importance: Notifications.AndroidImportance.HIGH,
  }).catch(() => undefined);
}

/** Ask the OS for notification permission; returns whether it was granted. */
export async function requestNotificationPermission(): Promise<boolean> {
  try {
    const settings = await Notifications.getPermissionsAsync();
    if (settings.granted) return true;
    const requested = await Notifications.requestPermissionsAsync();
    return requested.granted;
  } catch {
    return false;
  }
}

/** Post a local notification (used to surface a recommendation in-app, docs/05 §6) AND record
 * it to the Notifications screen's history. History is recorded UNCONDITIONALLY — it's the
 * in-app activity log, and turning off OS push (Settings' own toggle) shouldn't also make an
 * event vanish from it — while the OS notification itself respects `postOsNotification`
 * (Settings' `pushEnabled`) and is best-effort regardless. `target` becomes
 * `notification.request.content.data.target` so `App.tsx`'s tap listener can navigate straight
 * to the relevant screen; it also travels on the history record for browsing back through
 * later, tap or not. */
export async function notifyRecommendation(
  title: string,
  body: string,
  kind: NotificationKind = 'other',
  target?: NotificationTarget,
  postOsNotification = true,
): Promise<void> {
  await recordNotification({ kind, title, body, target }).catch(() => undefined);
  if (!postOsNotification) return;
  try {
    await Notifications.scheduleNotificationAsync({
      content: { title, body, data: target ? { target } : undefined },
      trigger: null, // deliver immediately
    });
  } catch {
    // Best-effort: a notification failure must never break the dispatch flow.
  }
}
