/**
 * Recommendation card + algorithm-audit panel (docs/05 §2.1, DESIGN.md §Recommendation Card).
 *
 * Renders exactly what the engine returned for an ALLOCATED response: facility, tier, ETA
 * (flagged when the travel time is estimated — the maps-fallback "degraded" state, docs/04 §6),
 * available beds, capability match, and the traceable audit (weights + reason + search effort).
 * Nothing is computed here; every value comes straight off `AllocatedResponse` — except the
 * "Record arrival" action (FR22), the one write this card itself triggers, since it is the
 * natural place a dispatcher confirms the patient reached the facility.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { Linking, StyleSheet, View } from 'react-native';

import { AppText, Button, Card, InlineNotice } from '../../components';
import type { AllocatedResponse } from '../../services/types';
import { colors, radius, spacing } from '../../theme';
import { TIER_LABEL } from './constants';

function Metric({ label, value, unit }: { label: string; value: string; unit?: string }): React.ReactElement {
  return (
    <View style={styles.metric}>
      <AppText variant="overline" color="onSurfaceVariant">
        {label}
      </AppText>
      <View style={styles.metricValue}>
        <AppText variant="dataLg" color="clinicalTeal">
          {value}
        </AppText>
        {unit ? (
          <AppText variant="dataSm" color="onSurfaceVariant">
            {unit}
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

function AuditBar({ label, weight }: { label: string; weight: number }): React.ReactElement {
  return (
    <View style={styles.barRow}>
      <View style={styles.barHeader}>
        <AppText variant="dataSm" color="onSurfaceVariant">
          {label}
        </AppText>
        <AppText variant="dataSm" color="onSurfaceVariant">
          Weight: {weight.toFixed(2)}
        </AppText>
      </View>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${Math.round(weight * 100)}%` }]} />
      </View>
    </View>
  );
}

export function RecommendationCard({
  result,
  arrived,
  recordingArrival,
  arrivalError,
  onRecordArrival,
  onNavigate,
}: {
  result: AllocatedResponse;
  /** True once arrival was recorded (locally, or observed via the status poll) — FR22. */
  arrived: boolean;
  recordingArrival: boolean;
  arrivalError: string | null;
  /** Omitted (button hidden) when there is nothing to record arrival against, e.g. mid-redirect. */
  onRecordArrival?: () => void;
  /** Switches the screen into live in-app navigation (`LiveNavigationMap`) — this card never
   * hands off to an external maps app itself. */
  onNavigate: () => void;
}): React.ReactElement {
  const facility = result.recommended_facility;
  const weights = result.weight_vector;

  return (
    <View style={styles.wrapper}>
      <View style={[styles.banner, arrived ? styles.bannerArrived : null]}>
        <MaterialIcons
          name={arrived ? 'task-alt' : 'check-circle'}
          size={22}
          color={colors.standardGreen}
        />
        <AppText variant="bodySm" color="onSurface" style={styles.bannerText}>
          {arrived ? 'Patient arrived · admission recorded' : 'Bed allocated · dispatch now'}
        </AppText>
      </View>

      {onRecordArrival && !arrived ? (
        <View style={styles.arrivalBlock}>
          {arrivalError ? (
            <InlineNotice title="Could not record arrival" message={arrivalError} />
          ) : null}
          <Button
            label={recordingArrival ? 'Recording arrival…' : 'Record arrival'}
            icon="task-alt"
            variant="secondary"
            onPress={onRecordArrival}
            loading={recordingArrival}
          />
        </View>
      ) : null}

      <Card>
        <View style={styles.header}>
          <View style={styles.headerText}>
            <AppText variant="overline" color="clinicalTeal">
              Best clinical match
            </AppText>
            <AppText variant="headlineMd" color="slate900">
              {facility.name}
            </AppText>
          </View>
          <View style={styles.tierTag}>
            <AppText variant="label" color="criticalRed">
              {TIER_LABEL[facility.tier] ?? facility.tier}
            </AppText>
          </View>
        </View>

        <View style={styles.metrics}>
          <View style={styles.metric}>
            <AppText variant="overline" color="onSurfaceVariant">
              ETA {facility.is_estimated_travel_time ? '(est.)' : '(traffic)'}
            </AppText>
            <View style={styles.metricValue}>
              <AppText
                variant="dataLg"
                color={facility.is_estimated_travel_time ? 'urgentOrange' : 'clinicalTeal'}
              >
                {facility.travel_time_minutes.toFixed(1)}
              </AppText>
              <AppText variant="dataSm" color="onSurfaceVariant">
                min
              </AppText>
            </View>
          </View>
          <Metric label="Capacity" value={String(facility.available_beds)} unit="beds" />
          <Metric label="Match (ĉ)" value={result.capability_match.toFixed(2)} />
        </View>

        {facility.is_estimated_travel_time ? (
          <View style={styles.estNote}>
            <MaterialIcons name="info-outline" size={16} color={colors.urgentOrange} />
            <AppText variant="dataSm" color="urgentOrange">
              Travel time estimated (maps unavailable)
            </AppText>
          </View>
        ) : null}

        <View style={styles.contactRow}>
          <MaterialIcons name="place" size={18} color={colors.onSurfaceVariant} />
          <AppText variant="bodySm" color="onSurfaceVariant">
            {facility.latitude.toFixed(4)}, {facility.longitude.toFixed(4)} · {facility.contact_phone}
          </AppText>
        </View>

        <View style={styles.actions}>
          <Button
            label="Contact"
            icon="call"
            variant="secondary"
            onPress={() => void Linking.openURL(`tel:${facility.contact_phone}`)}
            style={styles.action}
          />
          <Button
            label="Navigate"
            icon="navigation"
            onPress={onNavigate}
            style={styles.action}
          />
        </View>
      </Card>

      <Card style={styles.audit}>
        <View style={styles.auditHeader}>
          <MaterialIcons name="insights" size={18} color={colors.onSurfaceVariant} />
          <AppText variant="bodySm" color="onSurface">
            Algorithm Audit
          </AppText>
          <View style={styles.spacer} />
          <AppText variant="dataSm" color="onSurfaceVariant">
            {result.algorithm_used}
          </AppText>
        </View>
        <AppText variant="bodySm" color="onSurfaceVariant" style={styles.reason}>
          {result.selection_reason}
        </AppText>
        {weights ? (
          <View style={styles.bars}>
            <AuditBar label="Travel time (w_t)" weight={weights.w_t} />
            <AuditBar label="Bed availability (w_b)" weight={weights.w_b} />
            <AuditBar label="Clinical match (w_c)" weight={weights.w_c} />
          </View>
        ) : (
          <AppText variant="dataSm" color="onSurfaceVariant">
            Greedy nearest-facility — no weight vector.
          </AppText>
        )}
        <View style={styles.candidates}>
          <AppText variant="overline" color="onSurfaceVariant">
            Candidates evaluated
          </AppText>
          <AppText variant="dataLg" color="clinicalTeal">
            {result.candidates_evaluated}
          </AppText>
        </View>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: spacing.cardGap },
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: colors.greenTint,
    borderRadius: radius.control,
    padding: 14,
  },
  bannerArrived: { opacity: 0.85 },
  bannerText: { flex: 1 },
  arrivalBlock: { gap: 8 },
  header: { flexDirection: 'row', justifyContent: 'space-between', gap: 10, marginBottom: 16 },
  headerText: { flex: 1, gap: 2 },
  tierTag: {
    backgroundColor: colors.redTint,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
    alignSelf: 'flex-start',
  },
  metrics: { flexDirection: 'row', justifyContent: 'space-between' },
  metric: { gap: 4 },
  metricValue: { flexDirection: 'row', alignItems: 'baseline', gap: 4 },
  estNote: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12 },
  contactRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 16 },
  actions: { flexDirection: 'row', gap: 12, marginTop: 16 },
  action: { flex: 1 },
  audit: { backgroundColor: colors.surfaceContainerLow, gap: 12 },
  auditHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  spacer: { flex: 1 },
  reason: {},
  bars: { gap: 10 },
  barRow: { gap: 4 },
  barHeader: { flexDirection: 'row', justifyContent: 'space-between' },
  barTrack: { height: 6, borderRadius: radius.pill, backgroundColor: colors.surfaceContainerHighest },
  barFill: { height: 6, borderRadius: radius.pill, backgroundColor: colors.clinicalTeal },
  candidates: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
});
