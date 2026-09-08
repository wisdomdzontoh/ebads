/**
 * Dispatch screen (docs/05 §2.1) — the dispatcher's primary, online surface, laid out like a
 * ride-hailing home screen: a full-screen Google map canvas, a floating EBADS header with the
 * live online pill, a GPS button, and a bottom sheet that walks form → searching → result.
 *
 * The map centre picks the patient location (or GPS does); urgency and bed type are chips in
 * the sheet; "Find nearest bed" submits to `POST /allocations` and the sheet then renders the
 * engine's recommendation or escalation verbatim. Submission is disabled offline (docs/05 §3):
 * the tab becomes the read-only informational view and no request leaves the device. The
 * screen never scores or ranks — it collects input and displays the engine's answer.
 *
 * Reservation lifecycle (FR20, FR22, FR24-27, docs/01 §7): once a bed is confirmed, the sheet
 * polls `GET /allocations/{id}` every `POLL_INTERVAL_MS` while online — there is no real push
 * channel from the engine (FR19's SMS/push gateways are log-only, docs/01 §3.6), so this is
 * how the app finds out the facility revoked the reservation. A revocation blocks the sheet
 * behind `RevocationBanner` until the dispatcher gets a new recommendation from their CURRENT
 * GPS position (not the original incident coordinates — the ambulance has likely moved).
 * "Record arrival" is the one write `RecommendationCard` itself triggers.
 *
 * "Navigate" switches the whole screen into `LiveNavigationMap` — a live, in-app, GPS-tracked
 * route to the recommended facility — instead of handing off to the external Google Maps app.
 * The dispatcher never leaves EBADS to get there and back.
 */

import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, type NavigationProp } from '@react-navigation/native';
import * as Location from 'expo-location';
import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleSheet,
  useWindowDimensions,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import {
  AppText,
  Button,
  ConfirmDialog,
  DraggableSheet,
  InlineNotice,
  SectionLabel,
  StatusPill,
} from '../components';
import { Screen } from '../components/Screen';
import type { RootTabParamList } from '../navigation/RootTabs';
import { ApiError } from '../services/api';
import { notifyRecommendation } from '../services/notifications';
import type { NotificationKind } from '../services/notificationHistory';
import type { AllocationResponse, BedType, Urgency } from '../services/types';
import { useAuth } from '../state/AuthContext';
import { useConnectivity } from '../state/ConnectivityContext';
import { useSettings } from '../state/SettingsContext';
import { colors, radius, shadow, spacing } from '../theme';
import { BedTypeSelector } from './dispatch/BedTypeSelector';
import { DispatchMap, type Coord, type MapFacility } from './dispatch/DispatchMap';
import { EscalationCard } from './dispatch/EscalationCard';
import { LiveNavigationMap } from './dispatch/LiveNavigationMap';
import { OfflineFacilities } from './dispatch/OfflineFacilities';
import { RecommendationCard } from './dispatch/RecommendationCard';
import { RevocationBanner } from './dispatch/RevocationBanner';
import { TriageSelector } from './dispatch/TriageSelector';

/** How often to poll a confirmed reservation for a revocation while it's showing (ms). There
 * is no push channel to react to instead — see the module docstring. */
const POLL_INTERVAL_MS = 20_000;

/** Peek height of the draggable bottom sheet when collapsed — tall enough to still show the
 * heading/coord chip (form) or the "New dispatch" button plus the top of the result card, so
 * collapsing it never hides which state the dispatcher is in. */
const SHEET_COLLAPSED_HEIGHT = 168;

export function DispatchScreen(): React.ReactElement {
  const { api } = useAuth();
  const { settings, connection } = useSettings();
  const { online } = useConnectivity();
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();

  const [coord, setCoord] = useState<Coord | null>(null);
  const [flyTo, setFlyTo] = useState<Coord | null>(null);
  const [urgency, setUrgency] = useState<Urgency | null>(null);
  const [bedType, setBedType] = useState<BedType | null>(null);
  const [result, setResult] = useState<AllocationResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [gpsError, setGpsError] = useState<string | null>(null);

  // Reservation lifecycle, tracked only for a CONFIRMED allocation (result.status === 'confirmed').
  const [allocationId, setAllocationId] = useState<string | null>(null);
  const [arrived, setArrived] = useState(false);
  const [recordingArrival, setRecordingArrival] = useState(false);
  const [arrivalError, setArrivalError] = useState<string | null>(null);
  const [revoked, setRevoked] = useState<{ reason: string | null } | null>(null);
  const [redirecting, setRedirecting] = useState(false);
  const [redirectError, setRedirectError] = useState<string | null>(null);
  // Live in-app navigation (replaces handing off to the external Google Maps app) — takes
  // over the full-screen map while active; the sheet collapses to nothing behind it.
  const [navigating, setNavigating] = useState(false);
  // Guards "New dispatch" while a CONFIRMED reservation is still held and unresolved — see
  // startNewDispatch's docstring below for why this is a confirm PROMPT, not a revoke action.
  const [confirmNewDispatch, setConfirmNewDispatch] = useState(false);

  const canSubmit = Boolean(online && coord && urgency && bedType) && !submitting;

  const resetLifecycle = (): void => {
    setAllocationId(null);
    setArrived(false);
    setArrivalError(null);
    setRevoked(null);
    setRedirecting(false);
    setRedirectError(null);
    setNavigating(false);
  };

  const beginNewDispatch = (): void => {
    setResult(null);
    setSubmitError(null);
    resetLifecycle();
  };

  /** "New dispatch" while a confirmed reservation is still outstanding — held at the facility,
   * not yet arrived, not yet revoked by them — silently abandons it if left unresolved,
   * something the facility only discovers once its own expiry (or the dispatcher happening to
   * call them) catches up. Note this can only ever be a CONFIRMATION prompt, not a "revoke and
   * proceed" one: revoking a reservation (FR24-27) is a facility-side action by design — a
   * dispatcher's own account has no permission to release a bed the facility is holding out
   * from under them (backend/app/api/routes/allocations.py::revoke_allocation requires
   * FacilityStaffDep). This makes the dispatcher consciously acknowledge the still-active hold
   * before moving on, which is the whole of what's achievable without granting dispatchers a
   * new authority the reservation protocol deliberately doesn't give them. */
  const startNewDispatch = (): void => {
    const hasActiveHold = allocationId !== null && !arrived && !revoked;
    if (hasActiveHold) {
      setConfirmNewDispatch(true);
      return;
    }
    beginNewDispatch();
  };

  const useGps = async (): Promise<Coord | null> => {
    setLocating(true);
    setGpsError(null);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setGpsError('Location access is off — enable it in system settings, or move the map.');
        return null;
      }
      const position = await Location.getCurrentPositionAsync({});
      const fix = { latitude: position.coords.latitude, longitude: position.coords.longitude };
      setCoord(fix);
      setFlyTo(fix);
      return fix;
    } catch {
      setGpsError('Could not read the device location. Move the map to set it instead.');
      return null;
    } finally {
      setLocating(false);
    }
  };

  // Every alert this screen fires is about the CURRENT dispatch, so tapping any of them (from
  // the OS tray, or from the Notifications screen's history) always lands back on Dispatch —
  // there is no per-notification detail view, just this screen's own live lifecycle state.
  // History is recorded regardless of `pushEnabled` — only the OS-level popup respects it.
  const notify = (title: string, body: string, kind: NotificationKind = 'other'): void => {
    void notifyRecommendation(title, body, kind, { screen: 'Dispatch' }, settings.pushEnabled);
  };

  const submit = async (): Promise<void> => {
    if (!coord || !urgency || !bedType) return;
    setSubmitting(true);
    setSubmitError(null);
    resetLifecycle();
    try {
      const response = await api.createAllocation({
        patient_lat: coord.latitude,
        patient_lon: coord.longitude,
        urgency,
        required_bed_type: bedType,
      });
      setResult(response);
      if (response.status === 'confirmed') {
        setAllocationId(response.id);
        const facility = response.recommended_facility;
        notify(
          'Bed allocated',
          `${facility.name} · ${facility.travel_time_minutes.toFixed(1)} min · ${facility.available_beds} beds`,
          'recommendation',
        );
      } else {
        notify('Manual decision required', response.selection_reason, 'escalation');
      }
    } catch (error) {
      // Shown inline in the sheet (Alert.alert is a silent no-op on web).
      setSubmitError(error instanceof ApiError ? error.message : 'Could not reach the engine.');
    } finally {
      setSubmitting(false);
    }
  };

  // Poll the confirmed allocation for a status change — specifically a revocation, since that
  // is the one thing the facility can do that needs the dispatcher's attention right now.
  // Stops on its own once arrived or revoked (nothing left to watch for), offline (nothing to
  // poll with), or the sheet moves on to a new dispatch (`allocationId` cleared).
  const pollingRef = useRef(false);
  useEffect(() => {
    if (!allocationId || !online || arrived || revoked) return;
    const interval = setInterval(() => {
      if (pollingRef.current) return; // never overlap polls
      pollingRef.current = true;
      void api
        .getAllocation(allocationId)
        .then((audit) => {
          if (audit.status === 'revoked') {
            setRevoked({ reason: audit.revocation_reason });
            notify(
              'Reservation withdrawn',
              'The facility withdrew this reservation. Get a new recommendation.',
              'revocation',
            );
          } else if (audit.status === 'arrived') {
            setArrived(true);
          }
          // refused/expired are terminal too, but no further app action applies to either —
          // the dispatcher already knows on the ground; nothing to poll for stops on its own
          // once neither branch above matches again next tick... (status won't change further).
        })
        .catch(() => {
          // A transient poll failure must never interrupt the dispatcher — try again next tick.
        })
        .finally(() => {
          pollingRef.current = false;
        });
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [allocationId, online, arrived, revoked, api]);

  const recordArrival = async (): Promise<void> => {
    if (!allocationId) return;
    setRecordingArrival(true);
    setArrivalError(null);
    try {
      await api.recordArrival(allocationId);
      setArrived(true);
    } catch (error) {
      setArrivalError(error instanceof ApiError ? error.message : 'Could not reach the engine.');
    } finally {
      setRecordingArrival(false);
    }
  };

  const getNewRecommendation = async (): Promise<void> => {
    if (!allocationId) return;
    setRedirecting(true);
    setRedirectError(null);
    try {
      const fix = await useGps();
      if (!fix) {
        setRedirectError('Could not read the device location — try again once GPS is available.');
        return;
      }
      const response = await api.reallocate(allocationId, {
        current_lat: fix.latitude,
        current_lon: fix.longitude,
      });
      setResult(response);
      setRevoked(null);
      if (response.status === 'confirmed') {
        setAllocationId(response.id); // resume polling against the NEW allocation
        setArrived(false);
        const facility = response.recommended_facility;
        notify(
          'New bed allocated',
          `${facility.name} · ${facility.travel_time_minutes.toFixed(1)} min · ${facility.available_beds} beds`,
          'recommendation',
        );
      } else {
        setAllocationId(null); // escalated — nothing left to poll
        notify('Manual decision required', response.selection_reason, 'escalation');
      }
    } catch (error) {
      setRedirectError(error instanceof ApiError ? error.message : 'Could not reach the engine.');
    } finally {
      setRedirecting(false);
    }
  };

  // Offline: the Dispatch tab becomes the read-only informational view. No form, no submit,
  // no allocation request can be issued (docs/05 §3). The banner is rendered by Screen.
  if (!online) {
    return (
      <Screen>
        <OfflineFacilities />
      </Screen>
    );
  }

  // Live in-app navigation takes over the whole screen — no external Google Maps hand-off
  // (docs/05's own ride-hailing framing: the map IS the app, not a launcher for another one).
  if (navigating && result?.status === 'confirmed') {
    const facility = result.recommended_facility;
    return (
      <LiveNavigationMap
        destination={{
          latitude: facility.latitude,
          longitude: facility.longitude,
          name: facility.name,
          contactPhone: facility.contact_phone,
        }}
        fallbackOrigin={coord}
        arrived={arrived}
        recordingArrival={recordingArrival}
        onRecordArrival={() => void recordArrival()}
        onExit={() => setNavigating(false)}
      />
    );
  }

  const resultFacility: MapFacility | null =
    result?.status === 'confirmed'
      ? {
          latitude: result.recommended_facility.latitude,
          longitude: result.recommended_facility.longitude,
          name: result.recommended_facility.name,
        }
      : null;

  return (
    <View style={styles.root}>
      <View style={StyleSheet.absoluteFill}>
        <DispatchMap coord={coord} onPick={setCoord} flyTo={flyTo} facility={resultFacility} />
      </View>

      {/* Floating connectivity pill only — no brand chip/title, leaving the map unobstructed
          (the tab bar already identifies the screen; the logo lives on launch/onboarding). */}
      <View style={[styles.header, { top: insets.top + 10 }]} pointerEvents="box-none">
        <StatusPill online={online} />
      </View>

      {/* GPS button, floating just above the sheet's collapsed peek height (ride-hailing
          "locate me") — fixed, not measured, since the sheet itself no longer resizes. */}
      {!result ? (
        <Pressable
          onPress={() => void useGps()}
          disabled={locating}
          accessibilityRole="button"
          accessibilityLabel="Use GPS to set the patient location"
          style={[styles.fab, { bottom: SHEET_COLLAPSED_HEIGHT + 14 }]}
        >
          {locating ? (
            <ActivityIndicator color={colors.clinicalTeal} size="small" />
          ) : (
            <MaterialIcons name="my-location" size={22} color={colors.clinicalTeal} />
          )}
        </Pressable>
      ) : null}

      {/* Bottom sheet: form → searching → result. Draggable (Bolt-style) from anywhere on the
          sheet, not just the handle, plus an explicit close (X) button — drag or tap down to
          collapse it to a peek and see more of the map, drag up to reopen it. Re-opens
          automatically whenever the content switches between the form and a result. */}
      <DraggableSheet
        collapsedHeight={SHEET_COLLAPSED_HEIGHT}
        expandedHeight={height * 0.64}
        resetKey={result ? 'result' : 'form'}
        style={styles.sheet}
        contentContainerStyle={styles.sheetContent}
        keyboardShouldPersistTaps="handled"
      >
        {result ? (
            <>
              <Button
                label="New dispatch"
                icon="arrow-back"
                variant="secondary"
                onPress={startNewDispatch}
              />
              {revoked ? (
                <RevocationBanner
                  reason={revoked.reason}
                  redirecting={redirecting}
                  redirectError={redirectError}
                  onGetNewRecommendation={() => void getNewRecommendation()}
                />
              ) : result.status === 'confirmed' ? (
                <RecommendationCard
                  // Keyed by allocation id so a NEW recommendation (a fresh submit, or a
                  // post-revocation reallocation) always remounts with its own "Confirm
                  // reservation" gate unconfirmed — never inheriting a previous one's tap.
                  key={result.id}
                  result={result}
                  arrived={arrived}
                  recordingArrival={recordingArrival}
                  arrivalError={arrivalError}
                  onRecordArrival={() => void recordArrival()}
                  onNavigate={() => setNavigating(true)}
                />
              ) : (
                <EscalationCard result={result} />
              )}
            </>
          ) : (
            <>
              <View style={styles.headingRow}>
                <View style={styles.headingText}>
                  <AppText variant="headlineLg" color="slate900">
                    Find a bed
                  </AppText>
                  <AppText variant="bodySm" color="onSurfaceVariant">
                    {Platform.OS === 'web'
                      ? 'Use GPS to set the patient location'
                      : 'Move the map to set the patient location'}
                  </AppText>
                </View>
                <View
                  style={[
                    styles.coordChip,
                    coord ? styles.coordChipSet : null,
                  ]}
                >
                  <MaterialIcons
                    name="place"
                    size={14}
                    color={coord ? colors.clinicalTeal : colors.slate400}
                  />
                  <AppText variant="dataSm" color={coord ? 'clinicalTeal' : 'slate400'}>
                    {coord
                      ? `${coord.latitude.toFixed(4)}, ${coord.longitude.toFixed(4)}`
                      : 'No location'}
                  </AppText>
                </View>
              </View>

              {gpsError ? <InlineNotice title="GPS unavailable" message={gpsError} /> : null}

              <SectionLabel>Urgency</SectionLabel>
              <TriageSelector value={urgency} onChange={setUrgency} />

              <SectionLabel>Required bed type</SectionLabel>
              <BedTypeSelector value={bedType} onChange={setBedType} />

              {connection.status !== 'ok' ? <ConnectionHint failed={connection.status === 'failed'} /> : null}
              {submitError ? <InlineNotice title="Dispatch failed" message={submitError} /> : null}

              <Button
                label={submitting ? 'Finding nearest bed…' : 'Find nearest bed'}
                icon="arrow-forward"
                onPress={() => void submit()}
                disabled={!canSubmit}
                loading={submitting}
                style={styles.cta}
              />
            </>
          )}
      </DraggableSheet>

      <ConfirmDialog
        visible={confirmNewDispatch}
        title="Reservation still held"
        message="The facility is still holding a bed for the current reservation — it hasn't been arrived or revoked. Starting a new dispatch won't release it; you'll need to call the facility directly if it's no longer needed."
        confirmLabel="Start new dispatch anyway"
        cancelLabel="Keep current reservation"
        destructive
        onConfirm={() => {
          setConfirmNewDispatch(false);
          beginNewDispatch();
        }}
        onCancel={() => setConfirmNewDispatch(false)}
      />
    </View>
  );
}

/**
 * Shown while the engine connection is unverified or failed its last test — points at the ONE
 * place to fix it (Settings) instead of letting the submit fail with a raw fetch error.
 * Lives in its own component so `useNavigation` is only called when the online form renders.
 */
function ConnectionHint({ failed }: { failed: boolean }): React.ReactElement {
  const navigation = useNavigation<NavigationProp<RootTabParamList>>();
  return (
    <Pressable onPress={() => navigation.navigate('Settings')} accessibilityRole="button">
      <InlineNotice
        tone={failed ? 'error' : 'info'}
        title={failed ? 'Engine connection failed its last test' : 'Engine connection not verified'}
        message="Tap to open Settings and run the connection test."
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: {
    position: 'absolute',
    left: spacing.marginMobile,
    right: spacing.marginMobile,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
  },
  fab: {
    position: 'absolute',
    right: 16,
    width: 48,
    height: 48,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceContainerLowest,
    alignItems: 'center',
    justifyContent: 'center',
    ...shadow.card,
  },
  sheet: {
    backgroundColor: colors.surfaceContainerLowest,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    ...shadow.card,
  },
  sheetContent: {
    paddingHorizontal: spacing.gutter,
    paddingTop: 8,
    paddingBottom: 18,
    gap: 14,
  },
  headingRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 10,
  },
  headingText: { flex: 1, gap: 2 },
  coordChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.outlineVariant,
    backgroundColor: colors.surfaceContainerLow,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  coordChipSet: {
    borderColor: colors.clinicalTeal,
    backgroundColor: colors.greenTint,
  },
  cta: { minHeight: 58, borderRadius: radius.card, ...shadow.primaryCta },
});
