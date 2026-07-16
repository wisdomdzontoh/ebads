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

/** Post a local notification (used to surface a recommendation in-app, docs/05 §6). */
export async function notifyRecommendation(title: string, body: string): Promise<void> {
  try {
    await Notifications.scheduleNotificationAsync({
      content: { title, body },
      trigger: null, // deliver immediately
    });
  } catch {
    // Best-effort: a notification failure must never break the dispatch flow.
  }
}
