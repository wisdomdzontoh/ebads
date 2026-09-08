/**
 * Facility detail sheet (docs/05 §2.2) — shown when a dispatcher taps a facility, on the map
 * marker or the list row. A bottom-sheet modal (not a full navigation push): it's a quick,
 * informational look-up from a screen that's fundamentally a list/map, not a multi-step flow,
 * so a sheet the dispatcher can dismiss with one tap back to exactly where they were is the
 * better fit than a stacked screen (docs/05's ride-hailing framing favours sheets over pushes
 * throughout — Dispatch's own result view is one). Read-only except for two actions: call the
 * facility, or open live in-app navigation to it (`LiveNavigationMap` — never an external maps
 * hand-off, same as Dispatch's own "Navigate").
 */

import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { Linking, Modal, Pressable, StyleSheet, View } from 'react-native';

import { AppText, Button } from '../../components';
import type { CachedFacility } from '../../services/cache';
import { colors, radius, shadow, spacing } from '../../theme';
import {
  availabilityTone,
  bedSummary,
  TONE_COLOR,
  TONE_TINT,
  totalAvailable,
} from '../../utils/availability';
import { lastSyncLabel } from '../../utils/time';
import { TIER_LABEL } from '../dispatch/constants';

const BED_TYPE_LABEL: Record<string, string> = {
  general: 'General',
  icu: 'ICU',
  maternity_specialist: 'Maternity / Specialist',
};

export function FacilityDetailSheet({
  facility,
  onClose,
  onNavigate,
}: {
  facility: CachedFacility | null;
  onClose: () => void;
  onNavigate: (facility: CachedFacility) => void;
}): React.ReactElement {
  const open = facility !== null;
  const total = facility ? totalAvailable(facility.bed_counts) : 0;
  const tone = availabilityTone(total);

  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable
        style={styles.backdrop}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Close facility details"
      />
      {facility ? (
        <View style={styles.sheet}>
          <View style={styles.handle} />

          <View style={styles.header}>
            <View style={styles.headerText}>
              <AppText variant="headlineLg" color="slate900">
                {facility.name}
              </AppText>
              <AppText variant="dataSm" color="onSurfaceVariant">
                {TIER_LABEL[facility.tier] ?? facility.tier}
              </AppText>
            </View>
            <View style={[styles.totalBadge, { backgroundColor: TONE_TINT[tone] }]}>
              <AppText variant="dataLg" color={TONE_COLOR[tone]}>
                {total}
              </AppText>
              <AppText variant="overline" color={TONE_COLOR[tone]}>
                BEDS
              </AppText>
            </View>
          </View>

          <AppText variant="dataSm" color="onSurfaceVariant" style={styles.summaryLine}>
            {bedSummary(facility.bed_counts)}
          </AppText>

          <View style={styles.bedList}>
            {facility.bed_counts.map((bed) => {
              const pct = bed.capacity > 0 ? (bed.available / bed.capacity) * 100 : 0;
              return (
                <View key={bed.bed_type} style={styles.bedRow}>
                  <View style={styles.bedRowHeader}>
                    <AppText variant="bodySm" color="onSurface">
                      {BED_TYPE_LABEL[bed.bed_type] ?? bed.bed_type}
                    </AppText>
                    <AppText variant="dataSm" color="onSurfaceVariant">
                      {bed.available} / {bed.capacity}
                    </AppText>
                  </View>
                  <View style={styles.barTrack}>
                    <View style={[styles.barFill, { width: `${Math.min(100, Math.max(0, pct))}%` }]} />
                  </View>
                </View>
              );
            })}
          </View>

          <View style={styles.metaRow}>
            <MaterialIcons name="place" size={16} color={colors.onSurfaceVariant} />
            <AppText variant="dataSm" color="onSurfaceVariant">
              {facility.latitude.toFixed(4)}, {facility.longitude.toFixed(4)}
            </AppText>
          </View>
          <View style={styles.metaRow}>
            <MaterialIcons name="sync" size={16} color={colors.onSurfaceVariant} />
            <AppText variant="dataSm" color="onSurfaceVariant">
              Synced {lastSyncLabel(facility.synced_at)}
            </AppText>
          </View>

          <View style={styles.actions}>
            <Button
              label="Call"
              icon="call"
              variant="secondary"
              onPress={() => void Linking.openURL(`tel:${facility.contact_phone}`)}
              style={styles.action}
            />
            <Button
              label="Navigate"
              icon="navigation"
              onPress={() => onNavigate(facility)}
              style={styles.action}
            />
          </View>
        </View>
      ) : null}
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(16, 24, 38, 0.4)' },
  sheet: {
    backgroundColor: colors.surfaceContainerLowest,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 10,
    paddingHorizontal: spacing.gutter,
    paddingBottom: 28,
    gap: 14,
    ...shadow.card,
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.outlineVariant,
    alignSelf: 'center',
    marginBottom: 4,
  },
  header: { flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  headerText: { flex: 1, gap: 2 },
  totalBadge: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.control,
    paddingHorizontal: 14,
    paddingVertical: 8,
    gap: 0,
  },
  summaryLine: {},
  bedList: { gap: 10 },
  bedRow: { gap: 4 },
  bedRowHeader: { flexDirection: 'row', justifyContent: 'space-between' },
  barTrack: { height: 6, borderRadius: radius.pill, backgroundColor: colors.surfaceContainerHighest },
  barFill: { height: 6, borderRadius: radius.pill, backgroundColor: colors.clinicalTeal },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  actions: { flexDirection: 'row', gap: 12, marginTop: 4 },
  action: { flex: 1 },
});
