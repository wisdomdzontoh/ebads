/**
 * Required bed-type selector (docs/05 §2.1). Three tappable chips; the active one takes the
 * clinical-teal selection treatment (2px teal border + green tint). Captures input only.
 */

import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '../../components';
import type { BedType } from '../../services/types';
import { colors, radius } from '../../theme';
import { BED_TYPE_META } from './constants';

interface BedTypeSelectorProps {
  value: BedType | null;
  onChange: (bedType: BedType) => void;
}

export function BedTypeSelector({ value, onChange }: BedTypeSelectorProps): React.ReactElement {
  return (
    <View style={styles.row}>
      {BED_TYPE_META.map((meta) => {
        const selected = value === meta.value;
        return (
          <Pressable
            key={meta.value}
            onPress={() => onChange(meta.value)}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            accessibilityLabel={`${meta.label} bed`}
            style={[
              styles.chip,
              {
                borderColor: selected ? colors.clinicalTeal : colors.outlineVariant,
                borderWidth: selected ? 2 : 1,
                backgroundColor: selected ? colors.greenTint : colors.surfaceContainerLowest,
              },
            ]}
          >
            <AppText
              variant={selected ? 'headlineMd' : 'bodySm'}
              color={selected ? 'clinicalTeal' : 'onSurfaceVariant'}
            >
              {meta.label}
            </AppText>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 12 },
  chip: {
    flex: 1,
    height: 56,
    borderRadius: radius.control,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
