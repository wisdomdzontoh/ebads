/**
 * Revocation banner (FR24-27, docs/01 §7) — shown in place of the recommendation once polling
 * detects the receiving facility withdrew the reservation before arrival. Blocking by design:
 * there is no bed held for this patient anymore, so nothing else on the sheet is actionable
 * until the dispatcher gets a new recommendation from their CURRENT position — not the
 * original incident coordinates, which is why this asks GPS again rather than reusing `coord`.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText, Button, InlineNotice } from '../../components';
import { colors, radius, spacing } from '../../theme';

export function RevocationBanner({
  reason,
  redirecting,
  redirectError,
  onGetNewRecommendation,
}: {
  reason: string | null;
  redirecting: boolean;
  redirectError: string | null;
  onGetNewRecommendation: () => void;
}): React.ReactElement {
  return (
    <View style={styles.wrapper}>
      <View style={styles.banner}>
        <MaterialIcons name="report-problem" size={22} color={colors.criticalRed} />
        <View style={styles.bannerText}>
          <AppText variant="headlineMd" color="criticalRed">
            Reservation withdrawn
          </AppText>
          <AppText variant="bodySm" color="onSurfaceVariant">
            {reason
              ? `The facility withdrew this reservation: "${reason}"`
              : 'The facility withdrew this reservation before the patient arrived.'}{' '}
            Get a new recommendation from your current position.
          </AppText>
        </View>
      </View>

      {redirectError ? <InlineNotice title="Could not get a new recommendation" message={redirectError} /> : null}

      <Button
        label={redirecting ? 'Getting new recommendation…' : 'Get new recommendation'}
        icon="my-location"
        onPress={onGetNewRecommendation}
        loading={redirecting}
        style={styles.cta}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: spacing.cardGap },
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
  cta: { minHeight: 58, borderRadius: radius.card },
});
