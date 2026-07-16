/**
 * Dispatch map (native) — the full-screen Google map canvas of the ride-hailing-style
 * dispatch flow.
 *
 * Location is picked the way a ride-hailing app picks a pickup point: the map moves under a
 * fixed centre pin, and the map centre becomes the patient location once the dispatcher moves
 * the map (or uses GPS, which flies the camera). In the result state the centre pin gives way
 * to patient + facility markers and the camera fits both. This is pure input capture and
 * presentation — no distances or matching are computed here (docs/05 §8).
 */

import { MaterialIcons } from '@expo/vector-icons';
import React, { useEffect, useRef } from 'react';
import { StyleSheet, View } from 'react-native';
import MapView, { Marker, PROVIDER_GOOGLE } from 'react-native-maps';

import { AppText } from '../../components';
import { GOOGLE_MAPS_API_KEY } from '../../services/maps';
import { colors, radius, shadow } from '../../theme';

export interface Coord {
  latitude: number;
  longitude: number;
}

/** The engine's recommended facility, shown on the map in the result state. */
export interface MapFacility extends Coord {
  name: string;
}

interface DispatchMapProps {
  coord: Coord | null;
  onPick: (coord: Coord) => void;
  /** When set (GPS fix), the camera flies here; picking then follows the map centre. */
  flyTo: Coord | null;
  /** Non-null switches the canvas to the result state (markers instead of centre pin). */
  facility: MapFacility | null;
}

// Greater Accra default view when no location is chosen yet.
const DEFAULT_REGION = {
  latitude: 5.6037,
  longitude: -0.187,
  latitudeDelta: 0.18,
  longitudeDelta: 0.18,
};

// Camera span after a GPS fix — close enough to fine-tune by panning.
const PICK_DELTA = 0.04;

export function DispatchMap({
  coord,
  onPick,
  flyTo,
  facility,
}: DispatchMapProps): React.ReactElement {
  const mapRef = useRef<MapView | null>(null);
  const picking = facility === null;

  // GPS fix → fly the camera to it (the pick itself is set by the caller).
  useEffect(() => {
    if (flyTo) {
      mapRef.current?.animateToRegion(
        { ...flyTo, latitudeDelta: PICK_DELTA, longitudeDelta: PICK_DELTA },
        600,
      );
    }
  }, [flyTo]);

  // Result state → frame patient + facility together (sheet covers the lower part).
  useEffect(() => {
    if (facility && coord) {
      mapRef.current?.fitToCoordinates([coord, facility], {
        edgePadding: { top: 130, right: 60, bottom: 380, left: 60 },
        animated: true,
      });
    }
  }, [facility, coord]);

  return (
    <View style={styles.root}>
      <MapView
        ref={mapRef}
        style={styles.map}
        provider={PROVIDER_GOOGLE}
        initialRegion={coord ? { ...DEFAULT_REGION, ...coord } : DEFAULT_REGION}
        onRegionChangeComplete={(region, details) => {
          // Only a human gesture sets the location — programmatic camera moves (initial
          // layout, animateToRegion, fitToCoordinates) never silently pick a coordinate.
          if (picking && details?.isGesture) {
            onPick({ latitude: region.latitude, longitude: region.longitude });
          }
        }}
        showsUserLocation
        showsMyLocationButton={false}
        toolbarEnabled={false}
      >
        {facility && coord ? (
          <>
            <Marker coordinate={coord} title="Patient" pinColor={colors.clinicalTeal} />
            <Marker coordinate={facility} title={facility.name} />
          </>
        ) : null}
      </MapView>

      {picking ? (
        // Fixed centre pin: the glyph's tip must sit exactly on the map centre, so the wrapper
        // is centred and the glyph shifted up by half its height.
        <View pointerEvents="none" style={styles.pinLayer}>
          <MaterialIcons
            name="location-pin"
            size={48}
            color={coord ? colors.clinicalTeal : colors.slate400}
            style={styles.pin}
          />
        </View>
      ) : null}

      {!GOOGLE_MAPS_API_KEY ? (
        // A missing key renders Google Maps as a blank beige canvas — say so instead of
        // letting the dispatcher stare at an "invisible" map.
        <View pointerEvents="none" style={styles.keyWarning}>
          <AppText variant="dataSm" color="criticalRed" style={styles.keyWarningText}>
            Google Maps key missing — set EXPO_PUBLIC_GOOGLE_MAPS_API_KEY and rebuild the app.
          </AppText>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  map: { flex: 1 },
  pinLayer: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pin: { marginBottom: 44 }, // lift so the pin TIP touches the picked coordinate
  keyWarning: {
    position: 'absolute',
    top: 120,
    alignSelf: 'center',
    backgroundColor: colors.surfaceContainerLowest,
    borderRadius: radius.control,
    paddingHorizontal: 14,
    paddingVertical: 10,
    maxWidth: '86%',
    ...shadow.card,
  },
  keyWarningText: { textAlign: 'center' },
});
