/**
 * Dispatch map (web) — a Google Static Maps image standing in for the interactive canvas
 * (react-native-maps is native-only). Web cannot pan-to-pick, so the location comes from GPS;
 * the image centres on the picked coordinate and shows patient/facility markers. If the image
 * cannot load (missing key, key without the "Maps Static API" enabled, or referrer
 * restrictions) it says so explicitly — never an invisible broken image.
 */

import React, { useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';

import { AppText } from '../../components';
import { GOOGLE_MAPS_API_KEY, staticMapUrl } from '../../services/maps';
import { colors } from '../../theme';

export interface Coord {
  latitude: number;
  longitude: number;
}

export interface MapFacility extends Coord {
  name: string;
}

interface DispatchMapProps {
  coord: Coord | null;
  onPick: (coord: Coord) => void;
  flyTo: Coord | null;
  facility: MapFacility | null;
}

const ACCRA: Coord = { latitude: 5.6037, longitude: -0.187 };

function Unavailable({ message }: { message: string }): React.ReactElement {
  return (
    <View style={styles.box}>
      <AppText variant="dataSm" color="onSurfaceVariant" style={styles.boxText}>
        {message}
      </AppText>
    </View>
  );
}

export function DispatchMap({ coord, facility }: DispatchMapProps): React.ReactElement {
  const [failed, setFailed] = useState(false);

  if (!GOOGLE_MAPS_API_KEY) {
    return (
      <Unavailable message="Map unavailable — set EXPO_PUBLIC_GOOGLE_MAPS_API_KEY and restart the dev server. Location still works via 'Use GPS'." />
    );
  }
  if (failed) {
    return (
      <Unavailable message="Map image failed to load — the Google Maps key must have the 'Maps Static API' enabled and allow this site. Location still works via 'Use GPS'." />
    );
  }

  const markers = [
    ...(coord ? [{ ...coord, color: '0x0A616B' }] : []),
    ...(facility
      ? [{ latitude: facility.latitude, longitude: facility.longitude, color: 'red' }]
      : []),
  ];
  const url = staticMapUrl({
    center: facility ?? coord ?? ACCRA,
    zoom: facility ? 11 : coord ? 13 : 11,
    width: 640,
    height: 640,
    markers,
  });

  return (
    <Image
      source={{ uri: url }}
      style={styles.image}
      resizeMode="cover"
      onError={() => setFailed(true)}
      accessibilityLabel="Google map of the dispatch area"
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
