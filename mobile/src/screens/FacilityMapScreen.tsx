/**
 * Facility Map screen (docs/05 §2.2).
 *
 * A Google map of all facilities over a read-only, availability-coloured list — both sourced
 * from the LOCAL CACHE, so the screen works online and offline. It reloads when the tab gains
 * focus and whenever a sync completes. It renders cached data; it performs no matching and does
 * not re-order the list (docs/05 §8).
 */

import { useFocusEffect } from '@react-navigation/native';
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, View } from 'react-native';

import { AppText, Screen } from '../components';
import { loadFacilities, type CachedFacility } from '../services/cache';
import { useSync } from '../state/SyncContext';
import { colors, radius, shadow, spacing } from '../theme';
import { FacilityListItem } from './facilityMap/FacilityListItem';
import { FacilityMap } from './facilityMap/FacilityMap';

export function FacilityMapScreen(): React.ReactElement {
  const { lastSync } = useSync();
  const [facilities, setFacilities] = useState<CachedFacility[]>([]);
  // Distinguishes "cache not read yet" (spinner) from "cache is empty" (empty state), so the
  // empty-state message never flashes while the first read is in flight.
  const [loaded, setLoaded] = useState(false);

  const reload = useCallback(() => {
    void loadFacilities()
      .then(setFacilities)
      .catch(() => setFacilities([]))
      .finally(() => setLoaded(true));
  }, []);

  // Reload when the tab is focused, and whenever a sync updates the cache.
  useFocusEffect(reload);
  useEffect(reload, [reload, lastSync?.last_sync_at]);

  return (
    <Screen title="Facility Map" scroll={false} contentStyle={styles.content}>
      <View style={styles.mapArea}>
        <FacilityMap facilities={facilities} />
      </View>
      <View style={styles.sheet}>
        <View style={styles.handle} />
        <View style={styles.sheetHeader}>
          <AppText variant="headlineLg" color="slate900">
            Facility List
          </AppText>
          <View style={styles.totalChip}>
            <AppText variant="dataSm" color="onSurfaceVariant">
              {facilities.length} TOTAL
            </AppText>
          </View>
        </View>
        {!loaded ? (
          <View style={styles.loading}>
            <ActivityIndicator color={colors.clinicalTeal} />
          </View>
        ) : facilities.length === 0 ? (
          <AppText variant="bodySm" color="onSurfaceVariant">
            No cached facilities yet — sync from Settings while online.
          </AppText>
        ) : (
          <FlatList
            data={facilities}
            keyExtractor={(facility) => facility.id}
            renderItem={({ item }) => <FacilityListItem facility={item} />}
            ItemSeparatorComponent={() => <View style={styles.separator} />}
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={false}
          />
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { flex: 1 },
  mapArea: { height: '44%' },
  sheet: {
    flex: 1,
    backgroundColor: colors.surfaceContainerLowest,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    marginTop: -20,
    paddingTop: 12,
    paddingHorizontal: spacing.marginMobile,
    ...shadow.card,
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.outlineVariant,
    alignSelf: 'center',
    marginBottom: 14,
  },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  totalChip: {
    backgroundColor: colors.surfaceContainer,
    borderRadius: radius.sm,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  listContent: { paddingBottom: 24 },
  separator: { height: spacing.cardGap },
  loading: { paddingVertical: 24, alignItems: 'center' },
});
