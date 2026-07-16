/**
 * Urgency triage selector (DESIGN.md §Triage Selectors, docs/05 §2.1).
 *
 * Three large tappable cards; the active card takes its urgency's semantic colour (red/orange/
 * green) with a tint fill and a check badge, and shows the informational max-radius label.
 * This only captures the dispatcher's input — the engine decides everything downstream.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '../../components';
import type { Urgency } from '../../services/types';
import { colors, radius } from '../../theme';
import { URGENCY_META } from './constants';

interface TriageSelectorProps {
  value: Urgency | null;
  onChange: (urgency: Urgency) => void;
}

export function TriageSelector({ value, onChange }: TriageSelectorProps): React.ReactElement {
  return (
    <View style={styles.row}>
      {URGENCY_META.map((meta) => {
        const selected = value === meta.value;
        return (
          <Pressable
            key={meta.value}
            onPress={() => onChange(meta.value)}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            accessibilityLabel={`${meta.label} urgency, ${meta.radiusLabel}`}
            style={[
              styles.card,
              {
                borderColor: selected ? meta.color : colors.outlineVariant,
                borderWidth: selected ? 2 : 1,
                backgroundColor: selected ? meta.tint : colors.surfaceContainerLowest,
              },
            ]}
          >
            <AppText
              variant="headlineMd"
              style={{ color: selected ? meta.color : colors.onSurfaceVariant, opacity: selected ? 1 : 0.55 }}
            >
              {meta.label}
            </AppText>
            <AppText
              variant="dataSm"
              style={{ color: selected ? meta.color : colors.onSurfaceVariant, opacity: selected ? 0.85 : 0.5 }}
            >
              {meta.radiusLabel}
            </AppText>
            {selected ? (
              <View style={[styles.badge, { backgroundColor: meta.color }]}>
                <MaterialIcons name="check" size={13} color={colors.onPrimary} />
              </View>
            ) : null}
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 12 },
  card: {
    flex: 1,
    borderRadius: radius.control,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 2,
    minHeight: 84,
  },
  badge: {
    position: 'absolute',
    top: -8,
    right: -8,
    borderRadius: radius.pill,
    padding: 3,
  },
});
