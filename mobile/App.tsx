/**
 * App root — loads fonts and composes the provider stack around the navigation.
 *
 * Provider order matters: Settings (engine client + prefs) → Connectivity (online/offline) →
 * Sync (cache freshness, depends on the first two) → Navigation. The dual IBM Plex fonts are
 * loaded before render so every `AppText` variant has its family available (DESIGN.md
 * §Typography).
 */

import {
  IBMPlexMono_500Medium,
  IBMPlexMono_600SemiBold,
} from '@expo-google-fonts/ibm-plex-mono';
import {
  IBMPlexSans_400Regular,
  IBMPlexSans_600SemiBold,
  IBMPlexSans_700Bold,
} from '@expo-google-fonts/ibm-plex-sans';
import { createNavigationContainerRef, NavigationContainer } from '@react-navigation/native';
import { useFonts } from 'expo-font';
import * as Notifications from 'expo-notifications';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { LaunchScreen } from './src/components/LaunchScreen';
import { RootNavigator, type RootStackParamList } from './src/navigation/RootNavigator';
import { LoginScreen } from './src/screens/LoginScreen';
import { OnboardingScreen } from './src/screens/OnboardingScreen';
import type { NotificationTarget } from './src/services/notificationHistory';
import { AuthProvider, useAuth } from './src/state/AuthContext';
import { ConnectivityProvider } from './src/state/ConnectivityContext';
import { SettingsProvider, useSettings } from './src/state/SettingsContext';
import { SyncProvider } from './src/state/SyncContext';

// Held at module scope (not component state) so the notification-tap listener below — which
// must be registered once, outside any particular screen's lifetime — can navigate imperatively
// regardless of which screen happens to be mounted when a tap arrives.
const navigationRef = createNavigationContainerRef<RootStackParamList>();

// Keep the native splash up until the fonts are ready — no white flash in between.
void SplashScreen.preventAutoHideAsync().catch(() => undefined);

export default function App(): React.ReactElement | null {
  const [fontsLoaded, fontError] = useFonts({
    IBMPlexSans_400Regular,
    IBMPlexSans_600SemiBold,
    IBMPlexSans_700Bold,
    IBMPlexMono_500Medium,
    IBMPlexMono_600SemiBold,
  });

  const ready = fontsLoaded || Boolean(fontError);
  useEffect(() => {
    if (ready) void SplashScreen.hideAsync().catch(() => undefined);
  }, [ready]);

  // Tapping an OS notification (foreground, background, or one that launched the app cold)
  // navigates straight to what it's about, using the `target` every notification is posted
  // with (services/notifications.ts). Registered once at the app root — a per-screen listener
  // would only catch taps while that specific screen happened to be mounted.
  useEffect(() => {
    const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
      const target = response.notification.request.content.data?.target as
        | NotificationTarget
        | undefined;
      if (!target || !navigationRef.isReady()) return;
      navigationRef.navigate('MainTabs', { screen: target.screen });
    });
    return () => subscription.remove();
  }, []);

  // A font-loading failure must not strand the app on a blank screen — render with the
  // system fonts instead (the UI degrades visually, never functionally). While loading, show
  // the branded launch screen (web has no native splash, so this is its launch surface).
  if (!ready) return <LaunchScreen />;

  return (
    <SafeAreaProvider>
      <SettingsProvider>
        <AuthProvider>
          <ConnectivityProvider>
            <SyncProvider>
              <StatusBar style="dark" />
              <Root />
            </SyncProvider>
          </ConnectivityProvider>
        </AuthProvider>
      </SettingsProvider>
    </SafeAreaProvider>
  );
}

/**
 * Chooses the top surface once settings + auth have loaded: the one-time onboarding flow
 * until the dispatcher completes it, then `LoginScreen` until a session exists — an expired
 * refresh token drops back here from anywhere in the app, not just on first launch — then the
 * main tabbed app. Rendering nothing until both are `ready` avoids a flash of the wrong screen
 * while the persisted `onboarded` flag and session are read.
 */
function Root(): React.ReactElement | null {
  const { settings, ready: settingsReady } = useSettings();
  const { session, ready: authReady } = useAuth();
  if (!settingsReady || !authReady) return <LaunchScreen />;
  if (!settings.onboarded) return <OnboardingScreen />;
  if (!session) return <LoginScreen />;
  return (
    <NavigationContainer ref={navigationRef}>
      <RootNavigator />
    </NavigationContainer>
  );
}
