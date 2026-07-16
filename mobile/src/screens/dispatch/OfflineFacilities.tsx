/**
 * Offline informational view (docs/05 §3, DESIGN.md §Informational Mode).
 *
 * The strict offline boundary in visible form: a read-only list of cached facilities with their
 * last-known bed counts, capability tier, and phone number — enough for the dispatcher to make
 * an INFORMED manual phone call. "Call" is enabled; "Find bed" is disabled; and — critically —
 * this component never imports or calls the allocation API, so no matching request can fire
 * offline (docs/05 §8). The engine is the only thing that matches, and it is unreachable here.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, StyleSheet, View } from 'react-native';

import { AppText, Button, Card, SectionLabel } from '../../components';
import { loadFacilities, type CachedFacility } from '../../services/cache';
import type { BedType, Tier } from '../../services/types';
import { colors, radius, spacing } from '../../theme';

const BED_LABEL: Record<BedType, string> = {
  general: 'GEN WARD',
  icu: 'ICU BEDS',
  maternity_specialist: 'MATERNITY',
};

// Capability-tier tag (docs/05 §3 requires the tier to be shown for informed contact).
const TRIAGE: Record<Tier, { label: string; color: string; bg: string }> = {
  tertiary: { label: 'L3 · TERTIARY', color: colors.onSurfaceVariant, bg: colors.surfaceContainerHigh },
  secondary: { label: 'L2 · SECONDARY', color: colors.standardGreen, bg: colors.greenTint },
  primary: { label: 'L1 · PRIMARY', color: colors.urgentOrange, bg: colors.orangeTint },
};

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function OfflineFacilityCard({ facility }: { facility: CachedFacility }): React.ReactElement {
  const triage = TRIAGE[facility.tier];
  return (
    <Card style={styles.card}>
      <View style={styles.cardHeader}>
        <AppText variant="headlineMd" color="slate900" numberOfLines={1} style={styles.name}>
          {facility.name}
        </AppText>
        <View style={[styles.tag, { backgroundColor: triage.bg }]}>
          <AppText variant="label" style={{ color: triage.color }}>
            {triage.label}
          </AppText>
        </View>
      </View>

      <View style={styles.beds}>
        {facility.bed_counts.map((bed) => (
          <View key={bed.bed_type} style={styles.bedCol}>
            <AppText variant="overline" color="onSurfaceVariant">
              {BED_LABEL[bed.bed_type]}
            </AppText>
            <AppText variant="dataLg" color="slate900">
              {pad2(bed.available)}
            </AppText>
          </View>
        ))}
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
          label="Find bed"
          icon="hotel"
          variant="secondary"
          disabled
          onPress={() => undefined}
          style={styles.action}
        />
      </View>
    </Card>
  );
}

export function OfflineFacilities(): React.ReactElement {
  const [facilities, setFacilities] = useState<CachedFacility[]>([]);
  // "Not read yet" (spinner) vs "cache is empty" (empty state) — no empty-state flash.
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    void loadFacilities()
      .then(setFacilities)
      .catch(() => setFacilities([]))
      .finally(() => setLoaded(true));
  }, []);

  return (
    <View style={styles.container}>
      <SectionLabel>Cached facilities (read-only)</SectionLabel>
      {!loaded ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.clinicalTeal} />
        </View>
      ) : facilities.length === 0 ? (
        <AppText variant="bodySm" color="onSurfaceVariant">
          No cached facilities yet — connect once to sync.
        </AppText>
      ) : (
        facilities.map((facility) => <OfflineFacilityCard key={facility.id} facility={facility} />)
      )}
      <View style={styles.note}>
        <MaterialIcons name="block" size={18} color={colors.criticalRed} />
        <AppText variant="bodySm" color="slate900">
          Read-only · dispatch disabled until online
        </AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: spacing.cardGap },
  card: { gap: 16 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  name: { flex: 1 },
  tag: { borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 5 },
  beds: { flexDirection: 'row', justifyContent: 'space-between' },
  bedCol: { gap: 4 },
  actions: { flexDirection: 'row', gap: 12 },
  action: { flex: 1 },
  note: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: colors.surfaceContainer,
    borderRadius: radius.control,
    padding: 14,
    marginTop: spacing.base,
  },
  loading: { paddingVertical: 24, alignItems: 'center' },
});
