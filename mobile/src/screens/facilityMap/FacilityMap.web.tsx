/**
 * Facility map (web) — a Google Static Maps image with every cached facility as a coloured
 * marker (docs/05 §2.2). react-native-maps is native-only, so web uses the static image; it is
 * not interactive but shows the same Google Maps view with availability-coloured pins.
 */

import React, { useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';

import { AppText } from '../../components';
import type { CachedFacility } from '../../services/cache';
import { GOOGLE_MAPS_API_KEY, staticMapUrl } from '../../services/maps';
import { colors } from '../../theme';
import { availabilityTone, TONE_STATIC_COLOR, totalAvailable } from '../../utils/availability';

const ACCRA = { latitude: 5.62, longitude: -0.17 };

export function FacilityMap({ facilities }: { facilities: CachedFacility[] }): React.ReactElement {
  const [failed, setFailed] = useState(false);

  if (!GOOGLE_MAPS_API_KEY) {
    return (
      <View style={styles.box}>
        <AppText variant="dataSm" color="onSurfaceVariant" style={styles.boxText}>
          Map unavailable — set EXPO_PUBLIC_GOOGLE_MAPS_API_KEY and restart the dev server.
        </AppText>
      </View>
    );
  }
  if (failed) {
    return (
      <View style={styles.box}>
        <AppText variant="dataSm" color="onSurfaceVariant" style={styles.boxText}>
          Map image failed to load — the Google Maps key must have the &quot;Maps Static API&quot;
          enabled and allow this site. The facility list below still works.
        </AppText>
      </View>
    );
  }
  const markers = facilities.map((facility) => ({
    latitude: facility.latitude,
    longitude: facility.longitude,
    color: TONE_STATIC_COLOR[availabilityTone(totalAvailable(facility.bed_counts))],
  }));
  const url = staticMapUrl({ center: ACCRA, zoom: 11, width: 640, height: 480, markers });
  return (
    <Image
      source={{ uri: url }}
      style={styles.image}
      resizeMode="cover"
      onError={() => setFailed(true)}
      accessibilityLabel="Google map of all facilities"
    />
  );
}

const styles = StyleSheet.create({
  box: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    backgroundColor: colors.surfaceContainerLow,
  },
  boxText: { textAlign: 'center', maxWidth: 420 },
  image: { flex: 1, width: '100%' },
});
