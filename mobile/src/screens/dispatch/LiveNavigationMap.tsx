/**
 * Live in-app navigation (native) — replaces the old "Navigate" hand-off to the external
 * Google Maps app. A full-screen map that tracks the vehicle's live GPS position, draws the
 * real road route to the destination, and counts down a distance/ETA that is DERIVED FROM
 * that route (not a static number) — so it actually reflects progress, the way a ride-hailing
 * app's live navigation does, rather than a fire-and-forget hand-off to another app the
 * dispatcher then has to switch back from.
 *
 * GPS acquisition is `useLiveLocation` (hooks/useLiveLocation.ts) — a fast/cached/live fix
 * chain with an optional `fallbackOrigin` seed, because a slow or failed GPS fix previously
 * left this screen showing nothing at all: no route, no distance, no ETA, indefinitely.
 *
 * The route itself (`services/directions.ts`) is fetched once position is known (then
 * periodically refreshed, `ROUTE_REFRESH_MS`) — remaining distance/ETA between refreshes is
 * derived by scaling the live GPS-to-destination straight-line distance by the original
 * route's road/straight-line ratio, which tracks real progress (stalled traffic shows a
 * stalled ETA; the wrong direction shows a worsening one) without calling the Directions API
 * on every GPS tick. This is presentation math only — nothing here selects or ranks a facility
 * (docs/05 §8).
 */

import { MaterialIcons } from '@expo/vector-icons';
import React, { useEffect, useRef, useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import MapView, { Marker, Polyline, PROVIDER_GOOGLE } from 'react-native-maps';

import { AppText, Button, DraggableSheet, InlineNotice } from '../../components';
import { getRoute, type LatLng, type RouteResult } from '../../services/directions';
import { useLiveLocation } from '../../hooks/useLiveLocation';
import { colors, radius, shadow, spacing } from '../../theme';
import {
  FALLBACK_SPEED_MPS,
  formatDistanceMeters,
  formatDurationClock,
  haversineMeters,
} from '../../utils/distance';

const ROUTE_REFRESH_MS = 90_000;
const CAMERA_ZOOM_DELTA = 0.02;
// Peek height when the info sheet is dragged down — destination name/call button and the
// distance/ETA row stay visible, the same "route summary always showing" behaviour as Bolt's
// own collapsed ride-options sheet; drag up for GPS/route notices and the arrival button.
const INFO_SHEET_COLLAPSED_HEIGHT = 158;
const INFO_SHEET_EXPANDED_HEIGHT = 360;

export interface NavigationDestination extends LatLng {
  name: string;
  contactPhone: string;
}

interface LiveNavigationMapProps {
  destination: NavigationDestination;
  /** The incident/patient location, if known — seeds the map/route immediately instead of a
   * blank "waiting for GPS" state; swapped out the moment a real device fix arrives. Pass
   * `null` when there is no better starting guess than "wait for GPS" (e.g. browsing a
   * facility from the Map tab with no active dispatch). */
  fallbackOrigin: LatLng | null;
  /** Arrival tracking is only meaningful for an active dispatch — both omitted (button hidden)
   * when navigating from a context with no allocation to record arrival against. */
  arrived?: boolean;
  recordingArrival?: boolean;
  onRecordArrival?: () => void;
  onExit: () => void;
}

export function LiveNavigationMap({
  destination,
  fallbackOrigin,
  arrived = false,
  recordingArrival = false,
  onRecordArrival,
  onExit,
}: LiveNavigationMapProps): React.ReactElement {
  const mapRef = useRef<MapView | null>(null);
  const { position, usingFallback, error: locationError, retry } = useLiveLocation(fallbackOrigin);
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);
  // The road/straight-line ratio from the route the ETA/distance readout is scaled by between
  // Directions refreshes — captured once per fetched route, not recomputed per GPS tick.
  const circuityRef = useRef(1);
  // The periodic refresh below fires from a `setInterval` set up once per effect run; without a
  // ref it would keep re-fetching from the ORIGINAL position captured when the effect started
  // (a stale closure), never picking up where the vehicle actually is by the time 90s elapse.
  const positionRef = useRef(position);
  positionRef.current = position;

  // Fetch (and periodically refresh) the real road route once a position is known. Re-fetches
  // from a real GPS fix as soon as one supersedes the fallback, so the route the dispatcher is
  // actually directed along is never permanently anchored to a rough starting guess.
  useEffect(() => {
    if (!position) return;
    let cancelled = false;

    const fetchRoute = async (origin: LatLng): Promise<void> => {
      const { route: result, error } = await getRoute(origin, destination);
      if (cancelled) return;
      if (result) {
        setRoute(result);
        setRouteError(null);
        const straightLine = Math.max(1, haversineMeters(origin, destination));
        circuityRef.current = result.distanceMeters / straightLine;
      } else {
        // Surface Google's actual reason (e.g. "REQUEST_DENIED: ...") rather than a generic
        // message — a restricted API key looks identical to "no network" otherwise, see
        // services/directions.ts's module docstring.
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
    // Deliberately NOT re-running on every `position` tick while `usingFallback` is false (that
    // would re-fetch on every GPS update) — but DOES re-run the one time `usingFallback` flips
    // from true to false (a real fix superseding the seed), so navigation switches onto the
    // real route promptly instead of waiting up to 90s. The periodic in-interval refresh still
    // uses the LATEST position via `positionRef`, not this snapshot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Boolean(position), usingFallback, destination.latitude, destination.longitude]);

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
  // Falls back to a fixed average speed (matching the backend's own Haversine degradation) when
  // no real route has been fetched yet — otherwise the ETA sat at "—" indefinitely any time
  // Directions failed, which read as "live routing isn't working" even with good GPS and a
  // (straight-line) distance already showing.
  const averageSpeedMps = route
    ? route.distanceMeters / Math.max(1, route.durationSeconds)
    : FALLBACK_SPEED_MPS;
  const remainingSeconds =
    remainingMeters !== null && averageSpeedMps ? remainingMeters / averageSpeedMps : null;

  return (
    <View style={styles.root}>
      <MapView
        ref={mapRef}
        style={styles.map}
        provider={PROVIDER_GOOGLE}
        // Forces the LIGHT map style regardless of the device's system dark-mode setting — left
        // to "automatic" (the default), iOS renders the Google Maps chrome in dark mode whenever
        // the phone is in dark mode, which reads as broken/illegible against this light UI, not
        // as a deliberate theme. customMapStyle=[] pins the classic light Google style explicitly.
        userInterfaceStyle="light"
        customMapStyle={[]}
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
          // Thick, high-contrast route line (Bolt/Uber-style) — the previous 5px width read as
          // thin against a busy street map.
          <Polyline
            coordinates={route.path}
            strokeColor={colors.clinicalTeal}
            strokeWidth={8}
            lineCap="round"
            lineJoin="round"
          />
        ) : position ? (
          // No Directions route yet/unavailable — a straight line beats no line at all.
          <Polyline
            coordinates={[position, destination]}
            strokeColor={colors.slate400}
            strokeWidth={4}
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

      {/* Draggable info sheet (Bolt-style) — drag down to peek at just the route summary and see
          more of the map, drag up for GPS/route notices and the arrival button. */}
      <DraggableSheet
        collapsedHeight={INFO_SHEET_COLLAPSED_HEIGHT}
        expandedHeight={INFO_SHEET_EXPANDED_HEIGHT}
        style={styles.infoBar}
      >
        <ScrollView
          style={styles.infoScroll}
          contentContainerStyle={styles.infoScrollContent}
          showsVerticalScrollIndicator={false}
        >
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
              label={
                arrived ? 'Arrived' : recordingArrival ? 'Recording arrival…' : 'Record arrival'
              }
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
