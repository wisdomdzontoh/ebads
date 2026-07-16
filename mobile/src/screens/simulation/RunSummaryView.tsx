/**
 * Automatic-run summary (docs/05 §2.3, `automatic_run_summary` design).
 *
 * Renders the four engine-computed per-run metrics (ATBP / FRR / MCEE / CM, docs/07 §8) and the
 * allocated-vs-escalated outcome split. Every number comes from the `RunSummary` the engine
 * returned; the client only formats and lays them out.
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText, Button, Card } from '../../components';
import type { RunSummary, SimulationSessionRead } from '../../services/types';
import { colors, radius, spacing } from '../../theme';
import { formatMetric } from './constants';

function MetricCard({
  label,
  value,
  caption,
  color = colors.clinicalTeal,
}: {
  label: string;
  value: string;
  caption: string;
  color?: string;
}): React.ReactElement {
  return (
    <Card style={styles.metricCard}>
      <AppText variant="dataSm" color="onSurfaceVariant">
        {label}
      </AppText>
      <AppText variant="display" style={{ color, fontSize: 32, lineHeight: 36 }}>
        {value}
      </AppText>
      <AppText variant="dataSm" color="onSurfaceVariant">
        {caption}
      </AppText>
    </Card>
  );
}

export function RunSummaryView({
  summary,
  session,
  onReset,
}: {
  summary: RunSummary;
  session: SimulationSessionRead;
  onReset: () => void;
}): React.ReactElement {
  const { metrics } = summary;
  const allocatedFraction =
    metrics.events_total > 0 ? metrics.events_allocated / metrics.events_total : 0;

  return (
    <View style={styles.wrapper}>
      <View style={styles.header}>
        <AppText variant="headlineLg" color="slate900">
          Simulation
        </AppText>
        <View style={styles.tags}>
          <View style={styles.dot} />
          <AppText variant="bodySm" color="onSurface">
            Run complete · {metrics.events_total} events
          </AppText>
        </View>
        <View style={styles.chips}>
          <View style={styles.chip}>
            <AppText variant="dataSm" color="onSurfaceVariant">
              {session.algorithm_config}
            </AppText>
          </View>
          <View style={styles.chip}>
            <AppText variant="dataSm" color="onSurfaceVariant">
              occ {Math.round(session.occupancy_scenario * 100)}%
            </AppText>
          </View>
        </View>
      </View>

      <View style={styles.grid}>
        <MetricCard label="ATBP" value={formatMetric(metrics.atbp, 1)} caption="avg min to bed" />
        <MetricCard
          label="FRR"
          value={`${(metrics.frr * 100).toFixed(1)}%`}
          caption="rejection rate"
          color={colors.criticalRed}
        />
        <MetricCard label="MCEE" value={formatMetric(metrics.mcee, 1)} caption="candidates / event" color={colors.slate900} />
        <MetricCard label="CM" value={formatMetric(metrics.cm, 2)} caption="capability match" color={colors.slate900} />
      </View>

      <Card style={styles.outcomes}>
        <AppText variant="headlineMd" color="slate900">
          Outcomes
        </AppText>
        <View style={styles.bar}>
          <View style={[styles.barAllocated, { flex: Math.max(allocatedFraction, 0.001) }]} />
          <View style={[styles.barEscalated, { flex: Math.max(1 - allocatedFraction, 0.001) }]} />
        </View>
        <View style={styles.legend}>
          <View>
            <AppText variant="headlineMd" color="standardGreen">
              {metrics.events_allocated} allocated
            </AppText>
            <AppText variant="dataSm" color="onSurfaceVariant">
              Successful routing
            </AppText>
          </View>
          <View style={styles.legendRight}>
            <AppText variant="headlineMd" color="criticalRed">
              {metrics.events_escalated} escalated
            </AppText>
            <AppText variant="dataSm" color="onSurfaceVariant">
              Manual intervention
            </AppText>
          </View>
        </View>
      </Card>

      <Button label="New run" icon="refresh" onPress={onReset} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: spacing.sectionGap },
  header: { gap: 8 },
  tags: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dot: { width: 8, height: 8, borderRadius: radius.pill, backgroundColor: colors.standardGreen },
  chips: { flexDirection: 'row', gap: 8 },
  chip: {
    backgroundColor: colors.surfaceContainer,
    borderRadius: radius.sm,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.cardGap },
  metricCard: { width: '48%', gap: 4, flexGrow: 1 },
  outcomes: { gap: 16 },
  bar: { flexDirection: 'row', height: 28, borderRadius: radius.pill, overflow: 'hidden', gap: 3 },
  barAllocated: { backgroundColor: colors.standardGreen, borderRadius: radius.pill },
  barEscalated: { backgroundColor: colors.criticalRed, borderRadius: radius.pill },
  legend: { flexDirection: 'row', justifyContent: 'space-between' },
  legendRight: { alignItems: 'flex-end' },
});
