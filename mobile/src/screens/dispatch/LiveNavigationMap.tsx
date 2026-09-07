/**
 * Live in-app navigation (native) — replaces the old "Navigate" hand-off to the external
 * Google Maps app. A full-screen map that tracks the vehicle's live GPS position, draws the
 * real road route to the recommended facility, and counts down a distance/ETA that is
 * DERIVED FROM that route (not a static number) — so it actually reflects progress, the way a
 * ride-hailing app's live navigation does, rather than a fire-and-forget hand-off to another
 * app the dispatcher then has to switch back from.
 *
 * The route itself (`services/directions.ts`) is fetched once (then periodically refreshed,
 * `ROUTE_REFRESH_MS`) — remaining distance/ETA between refreshes is derived by scaling the
 * live GPS-to-destination straight-line distance by the original route's road/straight-line
 * ratio, which tracks real progress (stalled traffic shows a stalled ETA; the wrong direction
 * shows a worsening one) without calling the Directions API on every GPS tick. This is
 * presentation math only — nothing here selects or ranks a facility (docs/05 §8).
 */

import { MaterialIcons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import React, { useEffect, useRef, useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';
import MapView, { Marker, Polyline, PROVIDER_GOOGLE } from 'react-native-maps';

import { AppText, Button } from '../../components';
import { getRoute, type LatLng, type RouteResult } from '../../services/directions';
import { colors, radius, shadow, spacing } from '../../theme';
import { formatDistanceMeters, formatDurationClock, haversineMeters } from '../../utils/distance';

const ROUTE_REFRESH_MS = 90_000;
const CAMERA_ZOOM_DELTA = 0.02;

export interface NavigationDestination extends LatLng {
  name: string;
  contactPhone: string;
}

interface LiveNavigationMapProps {
  destination: NavigationDestination;
  arrived: boolean;
  recordingArrival: boolean;
  onRecordArrival: () => void;
  onExit: () => void;
}

export function LiveNavigationMap({
  destination,
  arrived,
  recordingArrival,
  onRecordArrival,
  onExit,
}: LiveNavigationMapProps): React.ReactElement {
  const mapRef = useRef<MapView | null>(null);
  const [position, setPosition] = useState<LatLng | null>(null);
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);
  // The road/straight-line ratio from the route the ETA/distance readout is scaled by between
  // Directions refreshes — captured once per fetched route, not recomputed per GPS tick.
  const circuityRef = useRef(1);

  // Live GPS track — the whole point of "in-app", not the one-shot fix Dispatch used to pick
  // the incident location.
  useEffect(() => {
    let subscription: Location.LocationSubscription | null = null;
    let active = true;
    void (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted' || !active) return;
      subscription = await Location.watchPositionAsync(
        { accuracy: Location.Accuracy.High, timeInterval: 3000, distanceInterval: 15 },
        (update) => {
          if (!active) return;
          setPosition({
            latitude: update.coords.latitude,
            longitude: update.coords.longitude,
          });
        },
      );
    })();
    return () => {
      active = false;
      subscription?.remove();
    };
  }, []);

  // Fetch (and periodically refresh) the real road route once a position is known.
  useEffect(() => {
    if (!position) return;
    let cancelled = false;

    const fetchRoute = async (origin: LatLng): Promise<void> => {
      const result = await getRoute(origin, destination);
      if (cancelled) return;
      if (result) {
        setRoute(result);
        setRouteError(null);
        const straightLine = Math.max(1, haversineMeters(origin, destination));
        circuityRef.current = result.distanceMeters / straightLine;
      } else {
        setRouteError('Live route unavailable — showing straight-line distance instead.');
      }
    };

    void fetchRoute(position);
    const interval = setInterval(() => void fetchRoute(position), ROUTE_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // Deliberately NOT re-running on every `position` tick (that would re-fetch on every GPS
    // update) — only the refresh interval re-fetches, using whatever position is current then.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Boolean(position), destination.latitude, destination.longitude]);

  // Follow the vehicle.
  useEffect(() => {
    if (!position) return;
    mapRef.current?.animateToRegion(
      { ...position, latitudeDelta: CAMERA_ZOOM_DELTA, longitudeDelta: CAMERA_ZOOM_DELTA },
      500,
    );
  }, [position]);

  const straightLineNow = position ? haversineMeters(position, destination) : null;
  const remainingMeters =
    straightLineNow !== null ? straightLineNow * circuityRef.current : null;
  const averageSpeedMps = route ? route.distanceMeters / Math.max(1, route.durationSeconds) : null;
  const remainingSeconds =
    remainingMeters !== null && averageSpeedMps ? remainingMeters / averageSpeedMps : null;

  return (
    <View style={styles.root}>
      <MapView
        ref={mapRef}
        style={styles.map}
        provider={PROVIDER_GOOGLE}
        initialRegion={{
          ...(position ?? destination),
          latitudeDelta: CAMERA_ZOOM_DELTA,
          longitudeDelta: CAMERA_ZOOM_DELTA,
        }}
        showsUserLocation
        showsMyLocationButton={false}
        toolbarEnabled={false}
      >
        <Marker coordinate={destination} title={destination.name} />
        {route ? (
          <Polyline coordinates={route.path} strokeColor={colors.clinicalTeal} strokeWidth={5} />
        ) : position ? (
          // No Directions route yet/unavailable — a straight line beats no line at all.
          <Polyline
            coordinates={[position, destination]}
            strokeColor={colors.slate400}
            strokeWidth={3}
            lineDashPattern={[8, 8]}
          />
        ) : null}
      </MapView>

      <Pressable
        onPress={onExit}
        accessibilityRole="button"
        accessibilityLabel="Exit navigation"
        style={styles.backButton}
      >
        <MaterialIcons name="arrow-back" size={22} color={colors.slate900} />
      </Pressable>

      <View style={styles.infoBar}>
        <View style={styles.infoHeader}>
          <AppText variant="headlineMd" color="slate900">
            {destination.name}
          </AppText>
          <Pressable
            onPress={() => void Linking.openURL(`tel:${destination.contactPhone}`)}
            accessibilityRole="button"
            accessibilityLabel={`Call ${destination.name}`}
            hitSlop={8}
          >
            <MaterialIcons name="call" size={22} color={colors.clinicalTeal} />
          </Pressable>
        </View>

        <View style={styles.metrics}>
          <View style={styles.metric}>
            <AppText variant="overline" color="onSurfaceVariant">
              Distance remaining
            </AppText>
            <AppText variant="dataLg" color="clinicalTeal">
              {remainingMeters !== null ? formatDistanceMeters(remainingMeters) : '—'}
            </AppText>
          </View>
          <View style={styles.metric}>
            <AppText variant="overline" color="onSurfaceVariant">
              ETA
            </AppText>
            <AppText variant="dataLg" color="clinicalTeal">
              {remainingSeconds !== null ? formatDurationClock(remainingSeconds) : '—'}
            </AppText>
          </View>
        </View>

        {routeError ? (
          <AppText variant="dataSm" color="urgentOrange">
            {routeError}
          </AppText>
        ) : null}
        {!position ? (
          <AppText variant="dataSm" color="onSurfaceVariant">
            Waiting for GPS…
          </AppText>
        ) : null}

        <Button
          label={
            arrived
              ? 'Arrived'
              : recordingArrival
                ? 'Recording arrival…'
                : 'Record arrival'
          }
          icon="task-alt"
          onPress={onRecordArrival}
          disabled={arrived}
          loading={recordingArrival}
          style={styles.arriveButton}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  map: { flex: 1 },
  backButton: {
    position: 'absolute',
    top: 54,
    left: spacing.marginMobile,
    width: 40,
    height: 40,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceContainerLowest,
    alignItems: 'center',
    justifyContent: 'center',
    ...shadow.card,
  },
  infoBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.surfaceContainerLowest,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingHorizontal: spacing.gutter,
    paddingTop: 16,
    paddingBottom: 24,
    gap: 12,
    ...shadow.card,
  },
  infoHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  metrics: { flexDirection: 'row', gap: 32 },
  metric: { gap: 4 },
  arriveButton: { minHeight: 52, borderRadius: radius.card, marginTop: 4 },
});
