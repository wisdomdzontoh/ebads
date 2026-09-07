/**
 * Dispatch history (docs/01 §7, `GET /allocations`) — the dispatcher's own past allocations,
 * newest first: what was requested, where it landed, and its current lifecycle status. A
 * read-only review surface (shift handoff, "what happened to that one") — the LIVE actions
 * (acknowledge/arrival/revocation-redirect) live on the Dispatch sheet while a case is still
 * active; this screen never mutates anything, it only lists what `listAllocations` returns.
 * Requires connectivity, like Simulation did — there is nothing to show offline that the
 * facility cache could stand in for (docs/05 §3).
 */

import { MaterialIcons } from '@expo/vector-icons';
import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';

import { AppText, Card, InlineNotice, Screen } from '../components';
import { ApiError } from '../services/api';
import { loadFacilities } from '../services/cache';
import type { AllocationAuditRead, AllocationStatus } from '../services/types';
import { useAuth } from '../state/AuthContext';
import { useConnectivity } from '../state/ConnectivityContext';
import { colors, radius, spacing } from '../theme';
import { BED_TYPE_META, URGENCY_META } from './dispatch/constants';

const URGENCY_COLOR = Object.fromEntries(URGENCY_META.map((u) => [u.value, u.color]));
const URGENCY_LABEL = Object.fromEntries(URGENCY_META.map((u) => [u.value, u.label]));
const BED_TYPE_LABEL = Object.fromEntries(BED_TYPE_META.map((b) => [b.value, b.label]));

const STATUS_LABEL: Record<AllocationStatus, string> = {
  pending: 'Pending',
  confirmed: 'Confirmed',
  arrived: 'Arrived',
  expired: 'Expired',
  refused: 'Refused',
  escalated: 'Escalated',
  revoked: 'Revoked',
};

const STATUS_TONE: Record<AllocationStatus, 'success' | 'error' | 'info'> = {
  pending: 'info',
  confirmed: 'info',
  arrived: 'success',
  expired: 'error',
  refused: 'error',
  escalated: 'error',
  revoked: 'error',
};

const TONE_COLOR = { success: colors.standardGreen, error: colors.criticalRed, info: colors.onSurfaceVariant };

export function HistoryScreen(): React.ReactElement {
  const { api } = useAuth();
  const { online } = useConnectivity();
  const [records, setRecords] = useState<AllocationAuditRead[] | null>(null);
  const [facilityNames, setFacilityNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const [list, facilities] = await Promise.all([
        api.listAllocations(),
        loadFacilities().catch(() => []),
      ]);
      setRecords(list);
      setFacilityNames(Object.fromEntries(facilities.map((f) => [f.id, f.name])));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the engine.');
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    if (online) void load();
  }, [online, load]);

  if (!online && !records) {
    return (
      <Screen title="History">
        <AppText variant="bodyLg" color="onSurfaceVariant">
          Dispatch history needs connectivity. Reconnect to load it.
        </AppText>
      </Screen>
    );
  }

  return (
    <Screen title="History" scroll={false}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={() => void load()} />}
      >
        {error ? <InlineNotice title="Could not load history" message={error} /> : null}
        {!error && records && records.length === 0 ? (
          <AppText variant="bodySm" color="onSurfaceVariant">
            No dispatches yet. Submitted allocations appear here.
          </AppText>
        ) : null}
        {loading && !records ? (
          <AppText variant="bodySm" color="onSurfaceVariant">
            Loading…
          </AppText>
        ) : null}
        {records?.map((record) => (
          <HistoryRow
            key={record.id}
            record={record}
            facilityName={record.facility_id ? facilityNames[record.facility_id] : null}
          />
        ))}
      </ScrollView>
    </Screen>
  );
}

function HistoryRow({
  record,
  facilityName,
}: {
  record: AllocationAuditRead;
  facilityName?: string | null;
}): React.ReactElement {
  const urgencyColor = record.urgency ? URGENCY_COLOR[record.urgency] : colors.slate400;
  const tone = STATUS_TONE[record.status];
  return (
    <Card style={styles.row}>
      <View style={[styles.urgencyBar, { backgroundColor: urgencyColor }]} />
      <View style={styles.rowContent}>
        <View style={styles.rowHeader}>
          <AppText variant="headlineMd" color="slate900">
            {facilityName ?? (record.facility_id ? 'Facility' : 'No facility')}
          </AppText>
          <View style={[styles.statusTag, { borderColor: TONE_COLOR[tone] }]}>
            <MaterialIcons
              name={tone === 'success' ? 'check-circle' : tone === 'error' ? 'error-outline' : 'schedule'}
              size={12}
              color={TONE_COLOR[tone]}
            />
            <AppText variant="label" color={TONE_COLOR[tone]}>
              {STATUS_LABEL[record.status]}
            </AppText>
          </View>
        </View>
        <AppText variant="dataSm" color="onSurfaceVariant">
          {record.urgency ? URGENCY_LABEL[record.urgency] : 'Unknown urgency'} ·{' '}
          {BED_TYPE_LABEL[record.required_bed_type]} bed ·{' '}
          {new Date(record.created_at).toLocaleString()}
        </AppText>
        {record.eta_minutes !== null ? (
          <AppText variant="dataSm" color="onSurfaceVariant">
            ETA {record.eta_minutes.toFixed(1)} min
            {record.is_estimated_travel_time ? ' (est.)' : ''}
          </AppText>
        ) : null}
        {record.status === 'revoked' && record.revocation_reason ? (
          <AppText variant="dataSm" color="criticalRed">
            Withdrawn: {record.revocation_reason}
          </AppText>
        ) : null}
        {record.status === 'escalated' ? (
          <AppText variant="dataSm" color="criticalRed">
            {record.selection_reason}
          </AppText>
        ) : null}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    gap: spacing.cardGap,
    paddingHorizontal: spacing.marginMobile,
    paddingTop: spacing.base,
    paddingBottom: 120,
  },
  row: { flexDirection: 'row', padding: 0, overflow: 'hidden' },
  urgencyBar: { width: 4 },
  rowContent: { flex: 1, padding: 14, gap: 4 },
  rowHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  statusTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
});
