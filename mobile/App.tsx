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
import { NavigationContainer } from '@react-navigation/native';
import { useFonts } from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { LaunchScreen } from './src/components/LaunchScreen';
import { RootTabs } from './src/navigation/RootTabs';
import { OnboardingScreen } from './src/screens/OnboardingScreen';
import { ConnectivityProvider } from './src/state/ConnectivityContext';
import { SettingsProvider, useSettings } from './src/state/SettingsContext';
import { SyncProvider } from './src/state/SyncContext';

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

  // A font-loading failure must not strand the app on a blank screen — render with the
  // system fonts instead (the UI degrades visually, never functionally). While loading, show
  // the branded launch screen (web has no native splash, so this is its launch surface).
  if (!ready) return <LaunchScreen />;

  return (
    <SafeAreaProvider>
      <SettingsProvider>
        <ConnectivityProvider>
          <SyncProvider>
            <StatusBar style="dark" />
            <Root />
          </SyncProvider>
        </ConnectivityProvider>
      </SettingsProvider>
    </SafeAreaProvider>
  );
}

/**
 * Chooses the top surface once settings have loaded: the one-time onboarding flow until the
 * dispatcher completes it, then the main tabbed app. Rendering nothing until `ready` avoids a
 * flash of the wrong screen while the persisted `onboarded` flag is read.
 */
function Root(): React.ReactElement | null {
  const { settings, ready } = useSettings();
  if (!ready) return <LaunchScreen />;
  if (!settings.onboarded) return <OnboardingScreen />;
  return (
    <NavigationContainer>
      <RootTabs />
    </NavigationContainer>
  );
}
