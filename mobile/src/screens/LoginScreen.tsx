/**
 * Sign-in screen (EBADS_PRD.md §10) — the auth gate `App.tsx` shows whenever there is no
 * session: first launch after onboarding, a signed-out state, or a refresh token that finally
 * expired. Deliberately NOT part of the one-time onboarding tour (`OnboardingScreen`) — a
 * session can lapse long after onboarding is behind the dispatcher, so this has to be able to
 * reappear on its own. No EBADS logo here (design pref: the mark is reserved for
 * launch/onboarding); the lightweight brand chip matches Dispatch's own header treatment.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { AppText, Button, InlineNotice } from '../components';
import { ApiError } from '../services/api';
import { normalizeBaseUrl, testConnection } from '../services/connection';
import { useAuth } from '../state/AuthContext';
import { useSettings } from '../state/SettingsContext';
import { colors, radius, shadow, spacing } from '../theme';
import { LabeledField, SecretField } from './settings/SettingRow';

export function LoginScreen(): React.ReactElement {
  const { login } = useAuth();
  const { settings, update, connection, setConnection } = useSettings();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editingUrl, setEditingUrl] = useState(false);
  const [baseUrl, setBaseUrl] = useState(settings.baseUrl);
  const [testing, setTesting] = useState(false);

  const canSubmit = email.trim().length > 0 && password.length > 0 && !submitting;

  const submit = async (): Promise<void> => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the engine.');
    } finally {
      setSubmitting(false);
    }
  };

  const saveUrlAndTest = async (): Promise<void> => {
    setTesting(true);
    const normalized = normalizeBaseUrl(baseUrl);
    setBaseUrl(normalized);
    await update({ baseUrl: normalized });
    const result = await testConnection(normalized);
    setConnection(
      result.ok
        ? { status: 'ok', message: null, checkedAt: new Date().toISOString() }
        : { status: 'failed', message: result.message, checkedAt: new Date().toISOString() },
    );
    setTesting(false);
    if (result.ok) setEditingUrl(false);
  };

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.brandChip}>
          <MaterialIcons name="emergency" size={18} color={colors.clinicalTeal} />
          <AppText variant="headlineMd" color="clinicalTeal">
            EBADS
          </AppText>
        </View>

        <View style={styles.heading}>
          <AppText variant="headlineLg" color="slate900">
            Sign in
          </AppText>
          <AppText variant="bodySm" color="onSurfaceVariant">
            Enter your dispatcher account credentials.
          </AppText>
        </View>

        <View style={styles.form}>
          <LabeledField
            label="Email"
            value={email}
            onChangeText={setEmail}
            icon="mail"
            placeholder="dispatcher@nas.gov.gh"
            keyboardType="default"
          />
          <SecretField label="Password" value={password} onChangeText={setPassword} />

          {error ? <InlineNotice title="Sign-in failed" message={error} /> : null}
          {connection.status === 'failed' && !editingUrl ? (
            <InlineNotice
              tone="info"
              title="Engine connection failed its last test"
              message={`${connection.message ?? ''} Tap "Change" below if the URL needs updating.`}
            />
          ) : null}

          <Button
            label={submitting ? 'Signing in…' : 'Sign in'}
            icon="arrow-forward"
            onPress={() => void submit()}
            disabled={!canSubmit}
            loading={submitting}
            style={styles.cta}
          />
        </View>

        <View style={styles.urlBlock}>
          {editingUrl ? (
            <View style={styles.form}>
              <LabeledField
                label="Engine base URL"
                value={baseUrl}
                onChangeText={setBaseUrl}
                icon="link"
                placeholder="http://host:8000/api/v1"
                keyboardType="url"
              />
              <View style={styles.urlActions}>
                <Button
                  label="Cancel"
                  variant="secondary"
                  onPress={() => {
                    setBaseUrl(settings.baseUrl);
                    setEditingUrl(false);
                  }}
                  style={styles.urlAction}
                />
                <Button
                  label={testing ? 'Testing…' : 'Save & test'}
                  onPress={() => void saveUrlAndTest()}
                  loading={testing}
                  style={styles.urlAction}
                />
              </View>
            </View>
          ) : (
            <Pressable onPress={() => setEditingUrl(true)} accessibilityRole="button" style={styles.urlRow}>
              <MaterialIcons name="link" size={16} color={colors.onSurfaceVariant} />
              <AppText variant="dataSm" color="onSurfaceVariant" style={styles.urlText}>
                {settings.baseUrl}
              </AppText>
              <AppText variant="dataSm" color="clinicalTeal">
                Change
              </AppText>
            </Pressable>
          )}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.surface },
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: spacing.gutter,
    paddingVertical: spacing.sectionGap,
    gap: spacing.sectionGap,
  },
  brandChip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'center',
    gap: 6,
    backgroundColor: colors.surfaceContainerLowest,
    borderRadius: radius.pill,
    paddingHorizontal: 14,
    paddingVertical: 8,
    ...shadow.card,
  },
  heading: { alignItems: 'center', gap: 4 },
  form: { gap: 14 },
  cta: { minHeight: 58, borderRadius: radius.card, ...shadow.primaryCta, marginTop: 4 },
  urlBlock: { marginTop: 4 },
  urlRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  urlText: { flexShrink: 1 },
  urlActions: { flexDirection: 'row', gap: 12 },
  urlAction: { flex: 1 },
});
