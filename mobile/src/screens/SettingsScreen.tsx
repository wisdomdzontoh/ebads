/**
 * Settings screen (docs/05 §2.4).
 *
 * Configures the engine connection (base URL only — auth is a signed-in session now, not a
 * shared API key, Increment 1) with an EXPLICIT "Save & test" flow: the URL is committed and
 * immediately verified reachable, and the persistent verdict (connected / failed / untested)
 * is shown right here — so a misconfiguration is caught once, in Settings, with a precise
 * message, instead of leaking as fetch errors on other screens (docs/05 §5). Also: background
 * sync interval (default 15 min, docs/09 §11), a manual "Sync now" trigger with last-sync
 * status, the push preference, and the signed-in dispatcher's account (change password, sign
 * out).
 */

import { MaterialIcons } from '@expo/vector-icons';
import Constants from 'expo-constants';
import React, { useState } from 'react';
import { Pressable, StyleSheet, Switch, View } from 'react-native';

import { AppText, Button, Card, InlineNotice, SectionLabel } from '../components';
import { Screen } from '../components/Screen';
import { ApiError } from '../services/api';
import { normalizeBaseUrl, testConnection } from '../services/connection';
import { useAuth } from '../state/AuthContext';
import { DEFAULT_SYNC_INTERVAL_MINUTES, useSettings } from '../state/SettingsContext';
import { useSync } from '../state/SyncContext';
import { colors, radius, spacing } from '../theme';
import { formatClock } from '../utils/time';
import { LabeledField, SecretField } from './settings/SettingRow';

const SYNC_INTERVALS = [5, 15, 30, 60];

const ROLE_LABEL: Record<string, string> = {
  system_administrator: 'System Administrator',
  facility_administrator: 'Facility Administrator',
  facility_staff: 'Facility Staff',
  dispatcher: 'Dispatcher',
};

export function SettingsScreen(): React.ReactElement {
  const { settings, connection, update, setConnection } = useSettings();
  const { lastSync, syncing, lastError, syncNow } = useSync();

  // Local, editable copy of the URL — committed only by "Save & test", so a half-typed URL
  // never becomes the live client configuration.
  const [baseUrl, setBaseUrl] = useState(settings.baseUrl);
  const [testing, setTesting] = useState(false);

  const dirty = baseUrl.trim() !== settings.baseUrl;

  const saveAndTest = async (): Promise<void> => {
    setTesting(true);
    const normalizedUrl = normalizeBaseUrl(baseUrl);
    setBaseUrl(normalizedUrl);
    // Commit first (so the app uses what the dispatcher typed), then verify it live.
    await update({ baseUrl: normalizedUrl });
    const result = await testConnection(normalizedUrl);
    setConnection(
      result.ok
        ? { status: 'ok', message: null, checkedAt: new Date().toISOString() }
        : { status: 'failed', message: result.message, checkedAt: new Date().toISOString() },
    );
    setTesting(false);
  };

  return (
    <Screen title="Settings">
      <SectionLabel>Account</SectionLabel>
      <AccountCard />

      <SectionLabel>Connection</SectionLabel>
      <Card style={styles.card}>
        <LabeledField
          label="API base URL"
          value={baseUrl}
          onChangeText={setBaseUrl}
          icon="link"
          placeholder="http://host:8000/api/v1"
          keyboardType="url"
        />

        {connection.status === 'ok' ? (
          <InlineNotice
            tone="success"
            title="Reachable"
            message={`Engine verified · checked ${
              connection.checkedAt ? formatClock(connection.checkedAt) : '—'
            }${dirty ? ' — unsaved changes below, test again to apply.' : ''}`}
          />
        ) : connection.status === 'failed' ? (
          <InlineNotice
            title="Connection failed"
            message={`${connection.message ?? 'Unknown error.'}${
              connection.checkedAt ? ` (checked ${formatClock(connection.checkedAt)})` : ''
            }`}
          />
        ) : (
          <InlineNotice
            tone="info"
            title="Not verified yet"
            message="Save & test to confirm the app can reach the engine."
          />
        )}

        <Button
          label={testing ? 'Testing connection…' : dirty ? 'Save & test connection' : 'Test connection'}
          icon="cloud-done"
          onPress={() => void saveAndTest()}
          loading={testing}
        />
      </Card>

      <SectionLabel>Cache sync</SectionLabel>
      <Card style={styles.card}>
        <View style={styles.rowBetween}>
          <View style={styles.rowText}>
            <AppText variant="headlineMd" color="slate900">
              Sync interval
            </AppText>
            <AppText variant="bodySm" color="onSurfaceVariant">
              Background facility updates
            </AppText>
          </View>
        </View>
        <View style={styles.intervalRow}>
          {SYNC_INTERVALS.map((minutes) => {
            const selected = settings.syncIntervalMinutes === minutes;
            return (
              <Pressable
                key={minutes}
                onPress={() => update({ syncIntervalMinutes: minutes })}
                style={[
                  styles.intervalChip,
                  {
                    borderColor: selected ? colors.clinicalTeal : colors.outlineVariant,
                    borderWidth: selected ? 2 : 1,
                    backgroundColor: selected ? colors.greenTint : colors.surfaceContainerLowest,
                  },
                ]}
              >
                <AppText variant="dataSm" color={selected ? 'clinicalTeal' : 'onSurfaceVariant'}>
                  {minutes} min
                </AppText>
              </Pressable>
            );
          })}
        </View>

        <View
          style={[
            styles.statusBox,
            { backgroundColor: synced(lastSync) ? colors.greenTint : colors.surfaceContainer },
          ]}
        >
          <View style={styles.statusText}>
            <AppText variant="overline" color="onSurfaceVariant">
              Last sync
            </AppText>
            <AppText variant="dataSm" color={synced(lastSync) ? 'standardGreen' : 'onSurfaceVariant'}>
              {lastSync?.last_sync_at ? formatClock(lastSync.last_sync_at) : '—'} ·{' '}
              {lastSync?.status ?? 'never'} · {lastSync?.facility_count ?? 0} facilities
            </AppText>
            {lastError ? (
              <AppText variant="dataSm" color="criticalRed">
                {lastError}
              </AppText>
            ) : null}
          </View>
          <MaterialIcons
            name={synced(lastSync) ? 'check-circle' : 'sync-problem'}
            size={22}
            color={synced(lastSync) ? colors.standardGreen : colors.onSurfaceVariant}
          />
        </View>

        <Button
          label={syncing ? 'Syncing…' : 'Sync now'}
          icon="sync"
          onPress={() => void syncNow()}
          loading={syncing}
        />
      </Card>

      <SectionLabel>Notifications</SectionLabel>
      <Card style={styles.rowBetween}>
        <View style={styles.rowText}>
          <AppText variant="headlineMd" color="slate900">
            Push recommendations
          </AppText>
          <AppText variant="bodySm" color="onSurfaceVariant">
            Critical triage alerts and ETA updates
          </AppText>
        </View>
        <Switch
          value={settings.pushEnabled}
          onValueChange={(value) => void update({ pushEnabled: value })}
          trackColor={{ true: colors.clinicalTeal, false: colors.outlineVariant }}
          thumbColor={colors.surfaceContainerLowest}
        />
      </Card>

      <View style={styles.footer}>
        <AppText variant="dataSm" color="slate400">
          EBADS dispatcher · v{Constants.expoConfig?.version ?? '?'}
        </AppText>
        {settings.syncIntervalMinutes !== DEFAULT_SYNC_INTERVAL_MINUTES ? (
          <AppText variant="dataSm" color="slate400">
            (default interval is {DEFAULT_SYNC_INTERVAL_MINUTES} min)
          </AppText>
        ) : null}
      </View>
    </Screen>
  );
}

function synced(lastSync: { status: string; last_sync_at: string | null } | null): boolean {
  return lastSync?.status === 'success' && Boolean(lastSync.last_sync_at);
}

/** Signed-in identity + change-password + sign-out — collapsed to a short form by default so
 * Settings' primary content (connection, sync) is not pushed below the fold. */
function AccountCard(): React.ReactElement {
  const { session, logout, changePassword } = useAuth();
  const [changing, setChanging] = useState(false);
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (!session) {
    // Should not render (App.tsx gates the whole tabbed app on a session existing), but a
    // defensive render beats a crash if this ever changes.
    return (
      <Card>
        <AppText variant="bodySm" color="onSurfaceVariant">
          Not signed in.
        </AppText>
      </Card>
    );
  }

  const submit = async (): Promise<void> => {
    setError(null);
    if (next.length < 12) {
      setError('New password must be at least 12 characters.');
      return;
    }
    if (next !== confirm) {
      setError('New password and confirmation do not match.');
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(current, next);
      setDone(true);
      setCurrent('');
      setNext('');
      setConfirm('');
      setChanging(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not change the password.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card style={styles.card}>
      <View style={styles.rowBetween}>
        <View style={styles.rowText}>
          <AppText variant="headlineMd" color="slate900">
            {session.email}
          </AppText>
          <AppText variant="bodySm" color="onSurfaceVariant">
            {ROLE_LABEL[session.role] ?? session.role}
          </AppText>
        </View>
        <MaterialIcons name="account-circle" size={28} color={colors.clinicalTeal} />
      </View>

      {done ? <InlineNotice tone="success" title="Password changed" /> : null}

      {changing ? (
        <View style={styles.card}>
          <SecretField
            label="Current password"
            value={current}
            onChangeText={(text) => {
              setCurrent(text);
              setDone(false);
            }}
          />
          <SecretField
            label="New password (min. 12 characters)"
            value={next}
            onChangeText={(text) => {
              setNext(text);
              setDone(false);
            }}
          />
          <SecretField
            label="Confirm new password"
            value={confirm}
            onChangeText={(text) => {
              setConfirm(text);
              setDone(false);
            }}
          />
          {error ? <InlineNotice title="Could not change password" message={error} /> : null}
          <View style={styles.rowBetween}>
            <Button
              label="Cancel"
              variant="secondary"
              onPress={() => {
                setChanging(false);
                setError(null);
                setCurrent('');
                setNext('');
                setConfirm('');
              }}
              style={styles.action}
            />
            <Button
              label={submitting ? 'Saving…' : 'Save new password'}
              onPress={() => void submit()}
              loading={submitting}
              style={styles.action}
            />
          </View>
        </View>
      ) : (
        <View style={styles.rowBetween}>
          <Button
            label="Change password"
            icon="lock"
            variant="secondary"
            onPress={() => setChanging(true)}
            style={styles.action}
          />
          <Button
            label="Sign out"
            icon="logout"
            variant="secondary"
            onPress={() => void logout()}
            style={styles.action}
          />
        </View>
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { gap: 18 },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  rowText: { flex: 1, gap: 2 },
  action: { flex: 1 },
  intervalRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  intervalChip: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: radius.control,
    minWidth: 64,
    alignItems: 'center',
  },
  statusBox: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderRadius: radius.control,
    padding: 16,
    gap: 12,
  },
  statusText: { flex: 1, gap: 2 },
  footer: { alignItems: 'center', gap: 4, marginTop: spacing.base },
});
