/**
 * Facility map (native) — all cached facilities as Google Maps markers, coloured by bed
 * availability (docs/05 §2.2). Renders from the local cache, so it works online and offline
 * (tiles need network, but the markers/coordinates come from the cache). Marker colour is a
 * presentation lookup only — no matching happens here (docs/05 §8).
 */

import React from 'react';
import { StyleSheet } from 'react-native';
import MapView, { Marker, PROVIDER_GOOGLE } from 'react-native-maps';

import type { CachedFacility } from '../../services/cache';
import { availabilityTone, TONE_COLOR, totalAvailable } from '../../utils/availability';

// Greater Accra overview (matches GA_BBOX centre used by the engine).
const ACCRA_REGION = {
  latitude: 5.62,
  longitude: -0.17,
  latitudeDelta: 0.4,
  longitudeDelta: 0.4,
};

export function FacilityMap({ facilities }: { facilities: CachedFacility[] }): React.ReactElement {
  return (
    <MapView provider={PROVIDER_GOOGLE} style={styles.map} initialRegion={ACCRA_REGION}>
      {facilities.map((facility) => {
        const total = totalAvailable(facility.bed_counts);
        return (
          <Marker
            key={facility.id}
            coordinate={{ latitude: facility.latitude, longitude: facility.longitude }}
            title={facility.name}
            description={`${total} beds available · ${facility.tier}`}
            pinColor={TONE_COLOR[availabilityTone(total)]}
          />
        );
      })}
    </MapView>
  );
}

const styles = StyleSheet.create({ map: { flex: 1 } });
