/**
 * Escalation card (docs/05 §2.1, DESIGN.md §Escalation Card).
 *
 * Shown when the engine could not place the patient (ESCALATED). Renders the two engine-
 * provided fallbacks — nearest reachable facility (bed unavailable) and nearest available
 * facility beyond the radius — plus the manual-decision prompt. The dispatcher decides; the
 * app only surfaces the engine's structured escalation (docs/05 §8). Fallback phone numbers
 * are looked up in the local facility cache by id (a display join, not matching), so the
 * dispatcher can call directly — docs/05 §3 requires enough data for informed phone contact.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React, { useEffect, useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';

import { AppText, Button, Card } from '../../components';
import { loadFacilities } from '../../services/cache';
import type { EscalatedResponse, FacilityBrief } from '../../services/types';
import { colors, radius, spacing } from '../../theme';

function Fallback({
  index,
  caption,
  brief,
  tone,
  phone,
}: {
  index: string;
  caption: string;
  brief: FacilityBrief;
  tone: 'critical' | 'available';
  phone: string | null;
}): React.ReactElement {
  const hasBeds = brief.available_beds > 0;
  return (
    <View style={styles.fallbackBlock}>
      <AppText variant="overline" color="onSurfaceVariant">
        Fallback recommendation {index}
      </AppText>
      <Card>
        <View style={styles.fallbackHeader}>
          <View style={styles.fallbackText}>
            <AppText
              variant="overline"
              color={tone === 'critical' ? 'urgentOrange' : 'standardGreen'}
            >
              {caption}
            </AppText>
            <AppText variant="headlineMd" color="slate900">
              {brief.name}
            </AppText>
          </View>
          <View
            style={[
              styles.tag,
              { backgroundColor: tone === 'critical' ? colors.redTint : colors.orangeTint },
            ]}
          >
            <AppText variant="label" color={tone === 'critical' ? 'criticalRed' : 'urgentOrange'}>
              {tone === 'critical' ? 'NO BED' : 'OUTSIDE RADIUS'}
            </AppText>
          </View>
        </View>
        <View style={styles.metrics}>
          <View style={styles.metric}>
            <AppText variant="overline" color="onSurfaceVariant">
              Travel ETA
            </AppText>
            <View style={styles.metricValue}>
              <AppText variant="dataLg" color={tone === 'critical' ? 'slate900' : 'urgentOrange'}>
                {brief.travel_time_minutes.toFixed(1)}
              </AppText>
              <AppText variant="dataSm" color="onSurfaceVariant">
                min
              </AppText>
            </View>
          </View>
          <View style={styles.metric}>
            <AppText variant="overline" color="onSurfaceVariant">
              Bed status
            </AppText>
            <View style={styles.metricValue}>
              <AppText variant="dataLg" color={hasBeds ? 'standardGreen' : 'criticalRed'}>
                {brief.available_beds}
              </AppText>
              <AppText variant="dataSm" color="onSurfaceVariant">
                beds
              </AppText>
              <MaterialIcons
                name={hasBeds ? 'check-circle' : 'block'}
                size={16}
                color={hasBeds ? colors.standardGreen : colors.criticalRed}
              />
            </View>
          </View>
        </View>
        {phone ? (
          <Button
            label={`Call ${brief.name}`}
            icon="call"
            variant="secondary"
            onPress={() => void Linking.openURL(`tel:${phone}`)}
            style={styles.callButton}
          />
        ) : null}
      </Card>
    </View>
  );
}

export function EscalationCard({ result }: { result: EscalatedResponse }): React.ReactElement {
  // Phone numbers come from the cached facility profiles (id → contact_phone). Best-effort:
  // an empty cache only hides the call shortcut, never the escalation itself.
  const [phones, setPhones] = useState<Record<string, string>>({});
  useEffect(() => {
    void loadFacilities()
      .then((facilities) => {
        setPhones(Object.fromEntries(facilities.map((f) => [f.id, f.contact_phone])));
      })
      .catch(() => setPhones({}));
  }, []);

  const hasFallbacks =
    result.nearest_within_radius !== null || result.nearest_available_outside_radius !== null;

  return (
    <View style={styles.wrapper}>
      <View style={styles.banner}>
        <MaterialIcons name="error-outline" size={22} color={colors.criticalRed} />
        <View style={styles.bannerText}>
          <AppText variant="headlineMd" color="criticalRed">
            Manual decision required
          </AppText>
          <AppText variant="bodySm" color="onSurfaceVariant">
            {result.selection_reason}
          </AppText>
        </View>
      </View>

      {result.nearest_within_radius ? (
        <Fallback
          index="01"
          caption="Nearest within radius"
          brief={result.nearest_within_radius}
          tone="critical"
          phone={phones[result.nearest_within_radius.id] ?? null}
        />
      ) : null}
      {result.nearest_available_outside_radius ? (
        <Fallback
          index="02"
          caption="Nearest available (outside radius)"
          brief={result.nearest_available_outside_radius}
          tone="available"
          phone={phones[result.nearest_available_outside_radius.id] ?? null}
        />
      ) : null}

      {!hasFallbacks ? (
        <Card>
          <AppText variant="bodySm" color="onSurfaceVariant">
            The engine found no fallback facility to suggest. Coordinate placement by phone
            using the Map tab's facility list.
          </AppText>
        </Card>
      ) : null}

      <View style={styles.statusFooter}>
        <AppText variant="bodySm" color="onSurfaceVariant">
          The {result.algorithm_used.replace('_', '-')} algorithm evaluated{' '}
          {result.candidates_evaluated}{' '}
          {result.candidates_evaluated === 1 ? 'facility' : 'facilities'} and none met the
          criteria. Choose a fallback and coordinate by phone.
        </AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: spacing.sectionGap },
  banner: {
    flexDirection: 'row',
    gap: 12,
    backgroundColor: colors.redTint,
    borderLeftWidth: 4,
    borderLeftColor: colors.criticalRed,
    borderRadius: radius.control,
    padding: 16,
  },
  bannerText: { flex: 1, gap: 4 },
  fallbackBlock: { gap: 10 },
  fallbackHeader: { flexDirection: 'row', justifyContent: 'space-between', gap: 10, marginBottom: 16 },
  fallbackText: { flex: 1, gap: 2 },
  tag: { borderRadius: radius.sm, paddingHorizontal: 10, paddingVertical: 5, alignSelf: 'flex-start' },
  metrics: { flexDirection: 'row', gap: 40 },
  metric: { gap: 4 },
  metricValue: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  callButton: { marginTop: 16 },
  statusFooter: {
    backgroundColor: colors.surfaceContainer,
    borderRadius: radius.control,
    padding: 16,
  },
});
