/**
 * Onboarding flow (docs/05, onboarding_* designs) — shown once before the main app.
 *
 * Four steps: welcome (official EBADS logo), engine connection (base URL + API key with a live
 * test, so the app is verified-working before the dispatcher ever reaches a screen that needs
 * the engine), location permission, and notification permission. Every step after welcome is
 * skippable — the app degrades gracefully; a skipped step just defers that setup (connection
 * can be finished later in Settings). Completing the flow sets `onboarded` so it never shows
 * again.
 */

import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';

import { AppText, InlineNotice } from '../components';
import { testConnection } from '../services/connection';
import { requestNotificationPermission } from '../services/notifications';
import { DEFAULT_BASE_URL, useSettings } from '../state/SettingsContext';
import { colors } from '../theme';
import { OnboardingStep } from './onboarding/OnboardingStep';
import { LabeledField, SecretField } from './settings/SettingRow';

import * as Location from 'expo-location';

type Step = 'welcome' | 'connect' | 'location' | 'notifications';

const STEP_COUNT = 4;

export function OnboardingScreen(): React.ReactElement {
  const { settings, update, setConnection } = useSettings();
  const [step, setStep] = useState<Step>('welcome');
  const [busy, setBusy] = useState(false);

  // Connect-step fields, edited locally and committed when tested/skipped.
  const [baseUrl, setBaseUrl] = useState(settings.baseUrl || DEFAULT_BASE_URL);
  const [apiKey, setApiKey] = useState(settings.apiKey);
  const [connectError, setConnectError] = useState<string | null>(null);

  const finish = (): void => {
    void update({ onboarded: true });
  };

  const testAndContinue = async (): Promise<void> => {
    setBusy(true);
    setConnectError(null);
    // Save what was typed either way — the dispatcher should never have to retype it.
    await update({ baseUrl: baseUrl.trim(), apiKey: apiKey.trim() });
    const result = await testConnection(baseUrl, apiKey.trim());
    if (result.ok) {
      setConnection({
        status: 'ok',
        message: null,
        checkedAt: new Date().toISOString(),
        facilityCount: result.facilityCount,
      });
      setBusy(false);
      setStep('location');
    } else {
      setConnection({
        status: 'failed',
        message: result.message,
        checkedAt: new Date().toISOString(),
        facilityCount: null,
      });
      setConnectError(result.message);
      setBusy(false);
    }
  };

  const skipConnect = async (): Promise<void> => {
    // Keep whatever was typed so Settings starts from it, but leave the verdict untested.
    await update({ baseUrl: baseUrl.trim() || DEFAULT_BASE_URL, apiKey: apiKey.trim() });
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
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView contentContainerStyle={styles.connectScroll} keyboardShouldPersistTaps="handled">
          <OnboardingStep
            icon="cloud-done"
            title="Connect to the Engine"
            body="Point the app at your EBADS allocation engine. The connection is tested right now, so every screen works the moment you finish setup."
            primaryLabel={busy ? 'Testing connection…' : 'Test & continue'}
            onPrimary={() => void testAndContinue()}
            primaryLoading={busy}
            secondaryLabel="Skip for now (configure later in Settings)"
            onSecondary={() => void skipConnect()}
            progress={{ total: STEP_COUNT, index: 1 }}
            footer={
              <View style={styles.connectFields}>
                <LabeledField
                  label="Engine base URL"
                  value={baseUrl}
                  onChangeText={setBaseUrl}
                  icon="link"
                  placeholder="http://host:8000/api/v1"
                  keyboardType="url"
                />
                <SecretField
                  label="API key"
                  value={apiKey}
                  onChangeText={setApiKey}
                  placeholder="X-API-Key (blank if the engine has none)"
                />
                {connectError ? (
                  <InlineNotice title="Connection failed" message={connectError} />
                ) : null}
              </View>
            }
          />
        </ScrollView>
      </KeyboardAvoidingView>
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
  flex: { flex: 1, backgroundColor: colors.surface },
  connectScroll: { flexGrow: 1 },
  connectFields: { gap: 14 },
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
