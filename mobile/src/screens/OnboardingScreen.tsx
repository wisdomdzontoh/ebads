/**
 * Onboarding flow (docs/05, onboarding_* designs) — shown once before the main app.
 *
 * Four steps: welcome (official EBADS logo), engine connection (a live reachability test
 * against the fixed, build-time `ENGINE_BASE_URL` — services/env.ts — so the app is verified-
 * working before the dispatcher ever reaches a screen that needs the engine), location
 * permission, and notification permission. Signing in is a SEPARATE, later gate (`LoginScreen`,
 * shown by App.tsx once onboarding is done) — not part of this one-time tour, since a session
 * can expire and need renewing long after onboarding is behind the dispatcher. Every step
 * after welcome is skippable — the app degrades gracefully; a skipped step just defers that
 * check (it can be re-run later in Settings). Completing the flow sets `onboarded` so it never
 * shows again.
 */

import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText, InlineNotice } from '../components';
import { testConnection } from '../services/connection';
import { ENGINE_BASE_URL } from '../services/env';
import { requestNotificationPermission } from '../services/notifications';
import { useSettings } from '../state/SettingsContext';
import { colors } from '../theme';
import { OnboardingStep } from './onboarding/OnboardingStep';

import * as Location from 'expo-location';

type Step = 'welcome' | 'connect' | 'location' | 'notifications';

const STEP_COUNT = 4;

export function OnboardingScreen(): React.ReactElement {
  const { update, setConnection } = useSettings();
  const [step, setStep] = useState<Step>('welcome');
  const [busy, setBusy] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  const finish = (): void => {
    void update({ onboarded: true });
  };

  const testAndContinue = async (): Promise<void> => {
    setBusy(true);
    setConnectError(null);
    const result = await testConnection();
    if (result.ok) {
      setConnection({ status: 'ok', message: null, checkedAt: new Date().toISOString() });
      setBusy(false);
      setStep('location');
    } else {
      setConnection({
        status: 'failed',
        message: result.message,
        checkedAt: new Date().toISOString(),
      });
      setConnectError(result.message);
      setBusy(false);
    }
  };

  const skipConnect = (): void => {
    setConnectError(null);
    setStep('location');
  };

  const requestLocation = async (): Promise<void> => {
    setBusy(true);
    try {
      await Location.requestForegroundPermissionsAsync();
    } catch {
      // Permission dialogs can be dismissed; continue regardless.
    } finally {
      setBusy(false);
      setStep('notifications');
    }
  };

  const requestNotifications = async (): Promise<void> => {
    setBusy(true);
    const granted = await requestNotificationPermission();
    void update({ pushEnabled: granted });
    setBusy(false);
    finish();
  };

  if (step === 'welcome') {
    return (
      <OnboardingStep
        logo={require('../../assets/ebads_logo.png')}
        title="End No-Bed Syndrome"
        body="EBADS coordinates emergency bed allocation across the National Ambulance Service network, so every patient reaches a reachable facility with an available bed."
        primaryLabel="Get started"
        onPrimary={() => setStep('connect')}
        progress={{ total: STEP_COUNT, index: 0 }}
        footer={
          <View style={styles.badge}>
            <AppText variant="overline" color="clinicalTeal">
              National Ambulance Service protocol
            </AppText>
          </View>
        }
      />
    );
  }

  if (step === 'connect') {
    return (
      <OnboardingStep
        icon="cloud-done"
        title="Connect to the Engine"
        body="EBADS is checking it can reach the allocation engine now, so every screen works the moment you finish setup. You'll sign in with your dispatcher account next."
        primaryLabel={busy ? 'Testing connection…' : 'Test & continue'}
        onPrimary={() => void testAndContinue()}
        primaryLoading={busy}
        secondaryLabel="Skip for now (retest later in Settings)"
        onSecondary={skipConnect}
        progress={{ total: STEP_COUNT, index: 1 }}
        footer={
          <View style={styles.connectFields}>
            <AppText variant="dataSm" color="onSurfaceVariant" style={styles.urlText}>
              {ENGINE_BASE_URL}
            </AppText>
            {connectError ? <InlineNotice title="Connection failed" message={connectError} /> : null}
          </View>
        }
      />
    );
  }

  if (step === 'location') {
    return (
      <OnboardingStep
        icon="my-location"
        title="Enable Location Matching"
        body="EBADS uses your location to calculate accurate travel times to hospitals and find the nearest available beds in real time."
        primaryLabel="Allow location access"
        onPrimary={() => void requestLocation()}
        primaryLoading={busy}
        secondaryLabel="Not now"
        onSecondary={() => setStep('notifications')}
        progress={{ total: STEP_COUNT, index: 2 }}
      />
    );
  }

  return (
    <OnboardingStep
      icon="notifications-active"
      title="Never Miss a Recommendation"
      body="Receive instant push alerts for bed allocations, triage updates, and ETA changes even when the app is in the background."
      primaryLabel="Enable notifications"
      onPrimary={() => void requestNotifications()}
      primaryLoading={busy}
      secondaryLabel="Skip"
      onSecondary={finish}
      progress={{ total: STEP_COUNT, index: 3 }}
      footer={
        <View style={styles.security}>
          <AppText variant="overline" style={{ color: colors.surfaceContainerLowest }}>
            Dispatcher security
          </AppText>
          <AppText variant="bodySm" style={{ color: colors.surfaceContainerLowest }}>
            Alerts carry operational data only — facility, ETA, and bed counts. No patient
            identifiers ever appear in a notification.
          </AppText>
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
  connectFields: { gap: 10, alignItems: 'center' },
  urlText: { textAlign: 'center' },
  badge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.greenTint,
    borderRadius: 9999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  security: {
    backgroundColor: colors.slate900,
    borderRadius: 12,
    padding: 16,
    gap: 6,
  },
});
