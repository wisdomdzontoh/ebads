/**
 * Interactive step trace (docs/05 §2.3, `interactive_step_trace` design).
 *
 * Shows the engine's full decision for one event: the ranked candidates with their normalised
 * criteria (t̂ travel, b̂ beds, ĉ capability) and final score Φ, the selected facility, and the
 * weight vector in effect. Candidates arrive already ranked by the engine (lowest score first);
 * the client only renders — it does not rank or score (docs/05 §8).
 */

import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText, Button, Card } from '../../components';
import type { SimulationSessionRead, StepCandidate, StepTrace } from '../../services/types';
import { colors, radius, spacing } from '../../theme';

function Criterion({ label, value }: { label: string; value: string }): React.ReactElement {
  return (
    <View style={styles.criterion}>
      <AppText variant="overline" color="onSurfaceVariant">
        {label}
      </AppText>
      <AppText variant="dataLg" color="slate900">
        {value}
      </AppText>
    </View>
  );
}

function CandidateRow({
  candidate,
  rank,
  selected,
  name,
}: {
  candidate: StepCandidate;
  rank: number;
  selected: boolean;
  name: string;
}): React.ReactElement {
  return (
    <Card
      style={[
        styles.candidate,
        selected && { borderColor: colors.clinicalTeal, borderWidth: 2 },
      ]}
    >
      <View style={styles.rankRow}>
        <AppText variant="overline" color={selected ? 'clinicalTeal' : 'onSurfaceVariant'}>
          {`RANK ${String(rank).padStart(2, '0')}`}
          {selected ? ' — SELECTED' : ''}
        </AppText>
        {selected ? <MaterialIcons name="check-circle" size={18} color={colors.clinicalTeal} /> : null}
      </View>
      <AppText variant="headlineMd" color="slate900" numberOfLines={1}>
        {name}
      </AppText>
      <View style={styles.criteria}>
        <Criterion label="t̂ trav" value={candidate.t_hat.toFixed(2)} />
        <Criterion label="b̂ bed" value={candidate.b_hat.toFixed(2)} />
        <Criterion label="ĉ cap" value={candidate.c_hat.toFixed(1)} />
        <View style={styles.criterion}>
          <AppText variant="overline" color="onSurfaceVariant">
            Φ final
          </AppText>
          <AppText variant="dataLg" color={selected ? 'clinicalTeal' : 'slate900'}>
            {candidate.score.toFixed(3)}
          </AppText>
        </View>
      </View>
    </Card>
  );
}

export function StepTraceView({
  trace,
  session,
  facilityNames,
  stepping,
  complete,
  onStep,
  onReset,
}: {
  trace: StepTrace;
  session: SimulationSessionRead;
  facilityNames: Record<string, string>;
  stepping: boolean;
  complete: boolean;
  onStep: () => void;
  onReset: () => void;
}): React.ReactElement {
  const weights = trace.weight_vector;
  const weightLine = weights
    ? `w_t ${weights.w_t.toFixed(2)} · w_b ${weights.w_b.toFixed(2)} · w_c ${weights.w_c.toFixed(2)} · min-max over H_f`
    : 'greedy · ranked by travel time';

  return (
    <View style={styles.wrapper}>
      <Card style={styles.headerCard}>
        <View style={styles.headerTop}>
          <AppText variant="overline" color="onSurfaceVariant">
            Interactive trace
          </AppText>
          <View style={[styles.statusTag, trace.status === 'escalated' && styles.statusEscalated]}>
            <AppText variant="label" color={trace.status === 'escalated' ? 'criticalRed' : 'standardGreen'}>
              {trace.status.toUpperCase()}
            </AppText>
          </View>
        </View>
        <AppText variant="headlineLg" color="slate900">
          Event {trace.event_index + 1} / {session.events_planned}
        </AppText>
        <View style={styles.meta}>
          <Meta label="Policy" value={session.algorithm_config} />
          <Meta label="Occ" value={`${Math.round(session.occupancy_scenario * 100)}%`} />
          <Meta label="Seed" value={String(session.random_seed)} />
        </View>
      </Card>

      <AppText variant="overline" color="onSurfaceVariant">
        Candidate ranking engine
      </AppText>

      {trace.candidates.length === 0 ? (
        <Card>
          <AppText variant="bodySm" color="onSurfaceVariant">
            No candidate passed the hard filter — the engine escalated this event.
          </AppText>
        </Card>
      ) : (
        trace.candidates.map((candidate, index) => (
          <CandidateRow
            key={candidate.facility_id}
            candidate={candidate}
            rank={index + 1}
            selected={candidate.facility_id === trace.selected_facility_id}
            name={facilityNames[candidate.facility_id] ?? candidate.facility_id.slice(0, 8)}
          />
        ))
      )}

      <View style={styles.footer}>
        <AppText variant="dataSm" color="onSurfaceVariant">
          {weightLine}
        </AppText>
        <AppText variant="dataSm" color="onSurfaceVariant">
          Lower score Φ indicates higher priority
        </AppText>
      </View>

      <View style={styles.actions}>
        <Button label="Reset" icon="refresh" variant="secondary" onPress={onReset} style={styles.action} />
        <Button
          label={complete ? 'Complete' : 'Step event'}
          icon="skip-next"
          onPress={onStep}
          disabled={complete}
          loading={stepping}
          style={styles.action}
        />
      </View>
    </View>
  );
}

function Meta({ label, value }: { label: string; value: string }): React.ReactElement {
  return (
    <View style={styles.metaItem}>
      <AppText variant="overline" color="onSurfaceVariant">
        {label}
      </AppText>
      <AppText variant="dataSm" color="clinicalTeal">
        {value}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: spacing.cardGap },
  headerCard: { gap: 12 },
  headerTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  statusTag: {
    backgroundColor: colors.greenTint,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  statusEscalated: { backgroundColor: colors.redTint },
  meta: { flexDirection: 'row', gap: 24, borderTopWidth: 1, borderTopColor: colors.outlineVariant, paddingTop: 12 },
  metaItem: { gap: 2 },
  candidate: { gap: 12 },
  rankRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  criteria: { flexDirection: 'row', justifyContent: 'space-between' },
  criterion: { gap: 4 },
  footer: {
    backgroundColor: colors.surfaceContainer,
    borderRadius: radius.control,
    padding: 14,
    gap: 4,
    alignItems: 'center',
  },
  actions: { flexDirection: 'row', gap: 12, marginTop: spacing.base },
  action: { flex: 1 },
});
