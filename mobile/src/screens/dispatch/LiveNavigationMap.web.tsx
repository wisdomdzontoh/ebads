/**
 * Live in-app navigation — web counterpart of `LiveNavigationMap.tsx`.
 *
 * `react-native-maps` is native-only, so the map itself is a Static Maps image (same
 * degradation `DispatchMap.web.tsx` already uses) rather than a live-panning canvas — but the
 * distance/ETA readout IS fully live, via the same `useLiveLocation` hook the native screen
 * uses (`expo-location` works fine on web). This still replaces the external Google Maps
 * hand-off the web build previously used — everything stays in-app, the map image just
 * refreshes on a timer instead of panning continuously.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React, { useEffect, useRef, useState } from 'react';
import { Image, Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { AppText, Button, DraggableSheet, InlineNotice } from '../../components';
import { useLiveLocation } from '../../hooks/useLiveLocation';
import { getRoute, type LatLng, type RouteResult } from '../../services/directions';
import { GOOGLE_MAPS_API_KEY, staticMapUrl } from '../../services/maps';
import { colors, radius, shadow, spacing } from '../../theme';
import {
  FALLBACK_SPEED_MPS,
  formatDistanceMeters,
  formatDurationClock,
  haversineMeters,
} from '../../utils/distance';

// Duplicated from `LiveNavigationMap.tsx` rather than imported from it: that file pulls in
// `react-native-maps` (native-only), and importing FROM the platform sibling — even a
// type-only import that compiles away — risks confusing Metro's `.web.tsx` resolution for
// this file's own name. A three-field interface is cheap to keep in sync by hand.
export interface NavigationDestination extends LatLng {
  name: string;
  contactPhone: string;
}

const ROUTE_REFRESH_MS = 90_000;
// The static map image only needs to refresh when the vehicle has moved meaningfully — every
// GPS tick would just re-request the same-looking image.
const IMAGE_REFRESH_MS = 15_000;
const MAX_PATH_POINTS = 50; // keeps the Static Maps URL well under its length limit
// See LiveNavigationMap.tsx's matching constants.
const INFO_SHEET_COLLAPSED_HEIGHT = 158;
const INFO_SHEET_EXPANDED_HEIGHT = 360;

interface LiveNavigationMapProps {
  destination: NavigationDestination;
  fallbackOrigin: LatLng | null;
  arrived?: boolean;
  recordingArrival?: boolean;
  onRecordArrival?: () => void;
  onExit: () => void;
}

/** Evenly sample down to at most `max` points, always keeping the first and last. */
function decimate(points: LatLng[], max: number): LatLng[] {
  if (points.length <= max) return points;
  const step = (points.length - 1) / (max - 1);
  return Array.from({ length: max }, (_, i) => points[Math.round(i * step)]);
}

export function LiveNavigationMap({
  destination,
  fallbackOrigin,
  arrived = false,
  recordingArrival = false,
  onRecordArrival,
  onExit,
}: LiveNavigationMapProps): React.ReactElement {
  const { position, usingFallback, error: locationError, retry } = useLiveLocation(fallbackOrigin);
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState(false);
  const circuityRef = useRef(1);
  const lastImageAtRef = useRef(0);
  const [imageTick, setImageTick] = useState(0);
  // See LiveNavigationMap.tsx: without this, the periodic refresh below re-fetches from the
  // stale position captured when the effect started, not where the vehicle actually is.
  const positionRef = useRef(position);
  positionRef.current = position;

  // Refresh the static image on a timer while a position is known, independent of how often
  // the underlying GPS actually ticks.
  useEffect(() => {
    if (!position) return;
    const interval = setInterval(() => {
      lastImageAtRef.current = Date.now();
      setImageTick((tick) => tick + 1);
    }, IMAGE_REFRESH_MS);
    return () => clearInterval(interval);
  }, [Boolean(position)]);

  useEffect(() => {
    if (!position) return;
    let cancelled = false;
    const fetchRoute = async (origin: LatLng): Promise<void> => {
      const { route: result, error } = await getRoute(origin, destination);
      if (cancelled) return;
      if (result) {
        setRoute(result);
        setRouteError(null);
        setImageFailed(false);
        const straightLine = Math.max(1, haversineMeters(origin, destination));
        circuityRef.current = result.distanceMeters / straightLine;
      } else {
        // Surface Google's actual reason (e.g. "REQUEST_DENIED: ...") — see
        // services/directions.ts's module docstring on why a restricted key looks identical to
        // "no network" otherwise.
        setRouteError(error ?? 'Live route unavailable — showing straight-line distance instead.');
      }
    };
    void fetchRoute(position);
    const interval = setInterval(() => {
      if (positionRef.current) void fetchRoute(positionRef.current);
    }, ROUTE_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // See LiveNavigationMap.tsx's matching effect for why `usingFallback` is a dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Boolean(position), usingFallback, destination.latitude, destination.longitude]);

  const straightLineNow = position ? haversineMeters(position, destination) : null;
  const remainingMeters = straightLineNow !== null ? straightLineNow * circuityRef.current : null;
  // See LiveNavigationMap.tsx: falls back to a fixed average speed so ETA doesn't sit at "—"
  // indefinitely whenever Directions fails.
  const averageSpeedMps = route
    ? route.distanceMeters / Math.max(1, route.durationSeconds)
    : FALLBACK_SPEED_MPS;
  const remainingSeconds =
    remainingMeters !== null && averageSpeedMps ? remainingMeters / averageSpeedMps : null;

  const mapCenter = position ?? destination;
  const mapUrl = GOOGLE_MAPS_API_KEY
    ? staticMapUrl({
        center: mapCenter,
        zoom: 13,
        width: 640,
        height: 480,
        markers: [
          ...(position ? [{ ...position, color: '0x0A616B' }] : []),
          { ...destination, color: 'red' },
        ],
        path: route ? decimate(route.path, MAX_PATH_POINTS) : position ? [position, destination] : [],
      })
    : null;

  return (
    <View style={styles.root}>
      {mapUrl && !imageFailed ? (
        <Image
          key={imageTick}
          source={{ uri: mapUrl }}
          style={styles.map}
          resizeMode="cover"
          onError={() => setImageFailed(true)}
          accessibilityLabel="Live map showing the route to the recommended facility"
        />
      ) : (
        <View style={styles.mapUnavailable}>
          <AppText variant="dataSm" color="onSurfaceVariant" style={styles.centerText}>
            {GOOGLE_MAPS_API_KEY
              ? 'Map image unavailable — distance and ETA below are still live.'
              : 'Map unavailable — set EXPO_PUBLIC_GOOGLE_MAPS_API_KEY. Distance and ETA below are still live.'}
          </AppText>
        </View>
      )}

      <Pressable
        onPress={onExit}
        accessibilityRole="button"
        accessibilityLabel="Exit navigation"
        style={styles.backButton}
      >
        <MaterialIcons name="arrow-back" size={22} color={colors.slate900} />
      </Pressable>

      {/* Draggable info sheet (Bolt-style) — drag down to peek at just the route summary and see
          more of the map, drag up for GPS/route notices and the arrival button. */}
      <DraggableSheet
        collapsedHeight={INFO_SHEET_COLLAPSED_HEIGHT}
        expandedHeight={INFO_SHEET_EXPANDED_HEIGHT}
        style={styles.infoBar}
      >
      <ScrollView style={styles.infoScroll} contentContainerStyle={styles.infoScrollContent} showsVerticalScrollIndicator={false}>
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
              ETA{route ? '' : ' (estimated)'}
            </AppText>
            <AppText variant="dataLg" color="clinicalTeal">
              {remainingSeconds !== null ? formatDurationClock(remainingSeconds) : '—'}
            </AppText>
          </View>
        </View>

        {locationError ? (
          <InlineNotice title="GPS unavailable" message={locationError} />
        ) : usingFallback ? (
          <AppText variant="dataSm" color="urgentOrange">
            Using the incident location to start — refining once live GPS locks on.
          </AppText>
        ) : null}
        {locationError ? (
          <Button label="Retry GPS" icon="my-location" variant="secondary" onPress={retry} />
        ) : null}
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

        {onRecordArrival ? (
          <Button
            label={arrived ? 'Arrived' : recordingArrival ? 'Recording arrival…' : 'Record arrival'}
            icon="task-alt"
            onPress={onRecordArrival}
            disabled={arrived}
            loading={recordingArrival}
            style={styles.arriveButton}
          />
        ) : null}
      </ScrollView>
      </DraggableSheet>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  map: { flex: 1, width: '100%' },
  mapUnavailable: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    backgroundColor: colors.surfaceContainerLow,
  },
  centerText: { textAlign: 'center', maxWidth: 420 },
  backButton: {
    position: 'absolute',
    top: 24,
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
    backgroundColor: colors.surfaceContainerLowest,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    ...shadow.card,
  },
  infoScroll: { flex: 1 },
  infoScrollContent: {
    paddingHorizontal: spacing.gutter,
    paddingBottom: 24,
    gap: 12,
  },
  infoHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  metrics: { flexDirection: 'row', gap: 32 },
  metric: { gap: 4 },
  arriveButton: { minHeight: 52, borderRadius: radius.card, marginTop: 4 },
});
