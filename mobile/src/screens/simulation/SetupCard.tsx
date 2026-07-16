/**
 * Simulation setup (docs/05 §2.3) — pick the algorithm, occupancy, events, and seed, then run
 * automatically or step interactively. This only builds the session-create payload; the engine
 * runs the simulation.
 */

import React, { useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { AppText, Button, Card, SectionLabel } from '../../components';
import type { AlgorithmName, SimulationSessionCreate } from '../../services/types';
import { colors, radius } from '../../theme';
import { ALGORITHM_OPTIONS, DEFAULT_EVENTS, DEFAULT_SEED, OCCUPANCY_OPTIONS } from './constants';

interface SetupCardProps {
  loading: boolean;
  onRun: (config: SimulationSessionCreate) => void;
  onStep: (config: SimulationSessionCreate) => void;
}

function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}): React.ReactElement {
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.chip,
        {
          borderColor: selected ? colors.clinicalTeal : colors.outlineVariant,
          borderWidth: selected ? 2 : 1,
          backgroundColor: selected ? colors.greenTint : colors.surfaceContainerLowest,
        },
      ]}
    >
      <AppText variant="bodySm" color={selected ? 'clinicalTeal' : 'onSurfaceVariant'}>
        {label}
      </AppText>
    </Pressable>
  );
}

export function SetupCard({ loading, onRun, onStep }: SetupCardProps): React.ReactElement {
  const [algorithm, setAlgorithm] = useState<AlgorithmName>('urgency_adaptive');
  const [occupancy, setOccupancy] = useState(0.9);
  const [events, setEvents] = useState(String(DEFAULT_EVENTS));
  const [seed, setSeed] = useState(String(DEFAULT_SEED));

  const config = (): SimulationSessionCreate => ({
    algorithm_config: algorithm,
    occupancy_scenario: occupancy,
    // The engine requires events_planned > 0 — clamp instead of letting a stray "-5" 422.
    events_planned: Math.max(1, Number.parseInt(events, 10) || DEFAULT_EVENTS),
    random_seed: Number.parseInt(seed, 10) || DEFAULT_SEED,
  });

  return (
    <Card style={styles.card}>
      <View style={styles.group}>
        <SectionLabel>Algorithm</SectionLabel>
        <View style={styles.chipRow}>
          {ALGORITHM_OPTIONS.map((option) => (
            <Chip
              key={option.value}
              label={option.label}
              selected={algorithm === option.value}
              onPress={() => setAlgorithm(option.value)}
            />
          ))}
        </View>
      </View>

      <View style={styles.group}>
        <SectionLabel>Occupancy</SectionLabel>
        <View style={styles.chipRow}>
          {OCCUPANCY_OPTIONS.map((value) => (
            <Chip
              key={value}
              label={`${Math.round(value * 100)}%`}
              selected={occupancy === value}
              onPress={() => setOccupancy(value)}
            />
          ))}
        </View>
      </View>

      <View style={styles.numbers}>
        <View style={styles.numberField}>
          <SectionLabel>Events</SectionLabel>
          <TextInput
            value={events}
            onChangeText={setEvents}
            keyboardType="number-pad"
            style={styles.input}
          />
        </View>
        <View style={styles.numberField}>
          <SectionLabel>Seed</SectionLabel>
          <TextInput
            value={seed}
            onChangeText={setSeed}
            keyboardType="number-pad"
            style={styles.input}
          />
        </View>
      </View>

      <View style={styles.actions}>
        <Button
          label="Step interactive"
          icon="skip-next"
          variant="secondary"
          onPress={() => onStep(config())}
          disabled={loading}
          style={styles.action}
        />
        <Button
          label="Run automatic"
          icon="play-arrow"
          onPress={() => onRun(config())}
          loading={loading}
          style={styles.action}
        />
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { gap: 20 },
  group: { gap: 10 },
  chipRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: radius.control,
    alignItems: 'center',
    justifyContent: 'center',
  },
  numbers: { flexDirection: 'row', gap: 12 },
  numberField: { flex: 1, gap: 10 },
  input: {
    height: 44,
    borderWidth: 1,
    borderColor: colors.outlineVariant,
    borderRadius: radius.control,
    paddingHorizontal: 12,
    fontFamily: 'IBMPlexMono_500Medium',
    fontSize: 14,
    color: colors.slate900,
    backgroundColor: colors.surfaceContainerLowest,
  },
  actions: { flexDirection: 'row', gap: 12 },
  action: { flex: 1 },
});
