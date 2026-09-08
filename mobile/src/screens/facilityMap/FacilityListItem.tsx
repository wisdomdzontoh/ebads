/**
 * Facility list row (docs/05 §2.2) — availability badge, name, tier + per-bed-type summary.
 * Tinted by availability tone. Displays cached data only — it never matches — but tapping it
 * DOES open `FacilityDetailSheet` (the chevron was previously decorative; nothing responded
 * to a tap at all).
 */

import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '../../components';
import type { CachedFacility } from '../../services/cache';
import { colors, radius } from '../../theme';
import {
  availabilityTone,
  bedSummary,
  TONE_COLOR,
  TONE_TINT,
  totalAvailable,
} from '../../utils/availability';

export function FacilityListItem({
  facility,
  onPress,
}: {
  facility: CachedFacility;
  onPress: () => void;
}): React.ReactElement {
  const total = totalAvailable(facility.bed_counts);
  const tone = availabilityTone(total);
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${facility.name} details`}
      style={[styles.row, { backgroundColor: TONE_TINT[tone] }]}
    >
      <View style={[styles.badge, { borderColor: TONE_COLOR[tone] }]}>
        <AppText variant="dataLg" color={TONE_COLOR[tone]}>
          {total}
        </AppText>
      </View>
      <View style={styles.text}>
        <AppText variant="headlineMd" color="slate900" numberOfLines={1}>
          {facility.name}
        </AppText>
        <AppText variant="dataSm" color="onSurfaceVariant">
          {facility.tier.toUpperCase()} · {bedSummary(facility.bed_counts)}
        </AppText>
      </View>
      <MaterialIcons name="chevron-right" size={22} color={TONE_COLOR[tone]} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    padding: 12,
    borderRadius: radius.control,
  },
  badge: {
    width: 52,
    height: 52,
    borderRadius: radius.sm,
    borderWidth: 1.5,
    backgroundColor: colors.surfaceContainerLowest,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: { flex: 1, gap: 2 },
});
