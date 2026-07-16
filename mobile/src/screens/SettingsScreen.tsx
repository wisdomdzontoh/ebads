/**
 * Settings screen (docs/05 §2.4).
 *
 * Configures the engine connection (base URL + API key) with an EXPLICIT "Save & test" flow:
 * values are committed and immediately verified against the live engine, and the persistent
 * verdict (connected / failed / untested) is shown right here — so a misconfiguration is
 * caught once, in Settings, with a precise message, instead of leaking as fetch errors on
 * other screens (docs/05 §5). Also: background sync interval (default 15 min, docs/09 §11),
 * a manual "Sync now" trigger with last-sync status, and the push preference.
 */

import { MaterialIcons } from '@expo/vector-icons';
import Constants from 'expo-constants';
import React, { useState } from 'react';
import { Pressable, StyleSheet, Switch, View } from 'react-native';

import { AppText, Button, Card, InlineNotice, SectionLabel } from '../components';
import { Screen } from '../components/Screen';
import { normalizeBaseUrl, testConnection } from '../services/connection';
import { DEFAULT_SYNC_INTERVAL_MINUTES, useSettings } from '../state/SettingsContext';
import { useSync } from '../state/SyncContext';
import { colors, radius, spacing } from '../theme';
import { formatClock } from '../utils/time';
import { LabeledField, SecretField } from './settings/SettingRow';

const SYNC_INTERVALS = [5, 15, 30, 60];

export function SettingsScreen(): React.ReactElement {
  const { settings, connection, update, setConnection } = useSettings();
  const { lastSync, syncing, lastError, syncNow } = useSync();

  // Local, editable copies of the connection fields — committed only by "Save & test", so a
  // half-typed URL never becomes the live client configuration.
  const [baseUrl, setBaseUrl] = useState(settings.baseUrl);
  const [apiKey, setApiKey] = useState(settings.apiKey);
  const [testing, setTesting] = useState(false);

  const dirty = baseUrl.trim() !== settings.baseUrl || apiKey.trim() !== settings.apiKey;
  const synced = lastSync?.status === 'success' && lastSync.last_sync_at;

  const saveAndTest = async (): Promise<void> => {
    setTesting(true);
    const normalizedUrl = normalizeBaseUrl(baseUrl);
    const trimmedKey = apiKey.trim();
    setBaseUrl(normalizedUrl);
    // Commit first (so the app uses what the dispatcher typed), then verify it live.
    await update({ baseUrl: normalizedUrl, apiKey: trimmedKey });
    const result = await testConnection(normalizedUrl, trimmedKey);
    setConnection(
      result.ok
        ? {
            status: 'ok',
            message: null,
            checkedAt: new Date().toISOString(),
            facilityCount: result.facilityCount,
          }
        : {
            status: 'failed',
            message: result.message,
            checkedAt: new Date().toISOString(),
            facilityCount: null,
          },
    );
    setTesting(false);
  };

  return (
    <Screen title="Settings">
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
        <SecretField
          label="API key"
          value={apiKey}
          onChangeText={setApiKey}
          placeholder="X-API-Key (blank if the engine has none)"
        />

        {connection.status === 'ok' ? (
          <InlineNotice
            tone="success"
            title="Connected"
            message={`Engine verified · ${connection.facilityCount ?? 0} facilities · checked ${
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
            { backgroundColor: synced ? colors.greenTint : colors.surfaceContainer },
          ]}
        >
          <View style={styles.statusText}>
            <AppText variant="overline" color="onSurfaceVariant">
              Last sync
            </AppText>
            <AppText variant="dataSm" color={synced ? 'standardGreen' : 'onSurfaceVariant'}>
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
            name={synced ? 'check-circle' : 'sync-problem'}
            size={22}
            color={synced ? colors.standardGreen : colors.onSurfaceVariant}
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

const styles = StyleSheet.create({
  card: { gap: 18 },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  rowText: { flex: 1, gap: 2 },
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
