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
 */

import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, type NavigationProp } from '@react-navigation/native';
import * as Location from 'expo-location';
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  useWindowDimensions,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppText, Button, InlineNotice, SectionLabel, StatusPill } from '../components';
import { Screen } from '../components/Screen';
import type { RootTabParamList } from '../navigation/RootTabs';
import { ApiError } from '../services/api';
import { notifyRecommendation } from '../services/notifications';
import type { AllocationResponse, BedType, Urgency } from '../services/types';
import { useConnectivity } from '../state/ConnectivityContext';
import { useSettings } from '../state/SettingsContext';
import { colors, radius, shadow, spacing } from '../theme';
import { BedTypeSelector } from './dispatch/BedTypeSelector';
import { DispatchMap, type Coord, type MapFacility } from './dispatch/DispatchMap';
import { EscalationCard } from './dispatch/EscalationCard';
import { OfflineFacilities } from './dispatch/OfflineFacilities';
import { RecommendationCard } from './dispatch/RecommendationCard';
import { TriageSelector } from './dispatch/TriageSelector';

export function DispatchScreen(): React.ReactElement {
  const { api, settings, connection } = useSettings();
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
  const [sheetHeight, setSheetHeight] = useState(0);

  const canSubmit = Boolean(online && coord && urgency && bedType) && !submitting;

  const useGps = async (): Promise<void> => {
    setLocating(true);
    setGpsError(null);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setGpsError('Location access is off — enable it in system settings, or move the map.');
        return;
      }
      const position = await Location.getCurrentPositionAsync({});
      const fix = { latitude: position.coords.latitude, longitude: position.coords.longitude };
      setCoord(fix);
      setFlyTo(fix);
    } catch {
      setGpsError('Could not read the device location. Move the map to set it instead.');
    } finally {
      setLocating(false);
    }
  };

  const submit = async (): Promise<void> => {
    if (!coord || !urgency || !bedType) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await api.createAllocation({
        patient_lat: coord.latitude,
        patient_lon: coord.longitude,
        urgency,
        required_bed_type: bedType,
      });
      setResult(response);
      // Surface the engine's decision as a local notification (docs/05 §6), if enabled.
      if (settings.pushEnabled) {
        if (response.status === 'allocated') {
          const facility = response.recommended_facility;
          void notifyRecommendation(
            'Bed allocated',
            `${facility.name} · ${facility.travel_time_minutes.toFixed(1)} min · ${facility.available_beds} beds`,
          );
        } else {
          void notifyRecommendation('Manual decision required', response.selection_reason);
        }
      }
    } catch (error) {
      // Shown inline in the sheet (Alert.alert is a silent no-op on web).
      setSubmitError(error instanceof ApiError ? error.message : 'Could not reach the engine.');
    } finally {
      setSubmitting(false);
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

  const resultFacility: MapFacility | null =
    result?.status === 'allocated'
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

      {/* Floating header — text brand only (the logo lives on launch/onboarding). */}
      <View style={[styles.header, { top: insets.top + 10 }]} pointerEvents="box-none">
        <View style={styles.brandChip}>
          <MaterialIcons name="emergency" size={18} color={colors.clinicalTeal} />
          <AppText variant="headlineMd" color="clinicalTeal">
            EBADS
          </AppText>
        </View>
        <StatusPill online={online} />
      </View>

      {/* GPS button, floating just above the sheet (ride-hailing "locate me"). */}
      {!result ? (
        <Pressable
          onPress={() => void useGps()}
          disabled={locating}
          accessibilityRole="button"
          accessibilityLabel="Use GPS to set the patient location"
          style={[styles.fab, { bottom: sheetHeight + 14 }]}
        >
          {locating ? (
            <ActivityIndicator color={colors.clinicalTeal} size="small" />
          ) : (
            <MaterialIcons name="my-location" size={22} color={colors.clinicalTeal} />
          )}
        </Pressable>
      ) : null}

      {/* Bottom sheet: form → searching → result. */}
      <View
        style={styles.sheet}
        onLayout={(event) => setSheetHeight(event.nativeEvent.layout.height)}
      >
        <View style={styles.handle} />
        <ScrollView
          style={{ maxHeight: height * 0.66 }}
          contentContainerStyle={styles.sheetContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {result ? (
            <>
              <Button
                label="New dispatch"
                icon="arrow-back"
                variant="secondary"
                onPress={() => {
                  setResult(null);
                  setSubmitError(null);
                }}
              />
              {result.status === 'allocated' ? (
                <RecommendationCard result={result} />
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
        </ScrollView>
      </View>
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
    justifyContent: 'space-between',
  },
  brandChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.surfaceContainerLowest,
    borderRadius: radius.pill,
    paddingHorizontal: 14,
    paddingVertical: 8,
    ...shadow.card,
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
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.surfaceContainerLowest,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 10,
    ...shadow.card,
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.outlineVariant,
    alignSelf: 'center',
    marginBottom: 6,
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
