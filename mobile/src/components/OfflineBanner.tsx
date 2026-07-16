/**
 * `OfflineBanner` — the informational-mode banner (DESIGN.md §Components, docs/05 §3).
 *
 * Slate-900 background with white text: it states plainly that matching needs connectivity and
 * shows how stale the cached data is. Its presence is the visible half of the strict offline
 * boundary — the app renders cached facilities read-only and issues no allocation request while
 * it is shown.
 */

import { MaterialCommunityIcons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, View } from 'react-native';

import { useSync } from '../state/SyncContext';
import { colors, radius, spacing } from '../theme';
import { lastSyncLabel } from '../utils/time';
import { AppText } from './AppText';

export function OfflineBanner(): React.ReactElement {
  const { lastSync } = useSync();
  return (
    <View style={styles.banner}>
      <View style={styles.row}>
        <MaterialCommunityIcons name="cloud-off-outline" size={22} color={colors.clinicalTeal} />
        <View style={styles.text}>
          <AppText variant="headlineMd" color="onPrimary">
            Matching requires connectivity
          </AppText>
          <AppText variant="dataSm" color="slate400">
            No recommendation can be generated offline
          </AppText>
        </View>
      </View>
      <View style={styles.chip}>
        <AppText variant="dataSm" color="standardGreen">
          last sync · {lastSyncLabel(lastSync?.last_sync_at ?? null)}
        </AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: colors.slate900,
    paddingHorizontal: spacing.marginMobile,
    paddingVertical: 14,
    gap: 10,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  text: { flex: 1, gap: 2 },
  chip: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(10,97,107,0.18)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.sm,
  },
});
