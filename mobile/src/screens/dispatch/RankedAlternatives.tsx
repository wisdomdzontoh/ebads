/**
 * Ranked alternatives (docs/EBADS_PRD.md G1's "ranked, explicable" goal) — the runners-up from
 * the same scoring pass that produced the recommendation above, shown below it for the
 * dispatcher's own situational awareness. Purely informational: nothing here is tappable into
 * a new allocation — the reservation is already committed to the one facility on the main card
 * (docs/01 §7's atomic CAS), and the client never matches (docs/05 §8), so there is no "pick
 * this one instead" action to offer. Renders exactly what `AllocatedResponse.ranked_alternatives`
 * returned; nothing here is computed.
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText, Card } from '../../components';
import type { RankedAlternative } from '../../services/types';
import { colors, radius, spacing } from '../../theme';
import { TIER_LABEL } from './constants';

/** Second place is "#2", not "#1" again — rank is this item's position AFTER the winner. */
function AlternativeRow({
  alternative,
  rank,
}: {
  alternative: RankedAlternative;
  rank: number;
}): React.ReactElement {
  return (
    <View style={styles.row}>
      <View style={styles.rank}>
        <AppText variant="dataSm" color="onSurfaceVariant">
          #{rank}
        </AppText>
      </View>
      <View style={styles.rowText}>
        <AppText variant="bodySm" color="slate900" numberOfLines={1}>
          {alternative.name}
        </AppText>
        <AppText variant="dataSm" color="onSurfaceVariant">
          {TIER_LABEL[alternative.tier] ?? alternative.tier}
        </AppText>
      </View>
      <View style={styles.rowMetrics}>
        <AppText
          variant="dataSm"
          color={alternative.is_estimated_travel_time ? 'urgentOrange' : 'clinicalTeal'}
        >
          {alternative.travel_time_minutes.toFixed(1)} min
        </AppText>
        <AppText variant="dataSm" color="onSurfaceVariant">
          {alternative.available_beds} beds
        </AppText>
      </View>
    </View>
  );
}

export function RankedAlternatives({
  alternatives,
}: {
  alternatives: RankedAlternative[];
}): React.ReactElement | null {
  if (alternatives.length === 0) return null;
  return (
    <Card style={styles.card}>
      <AppText variant="bodySm" color="onSurface">
        Ranked alternatives
      </AppText>
      <AppText variant="dataSm" color="onSurfaceVariant" style={styles.subtitle}>
        Other candidates from the same search, not reserved.
      </AppText>
      <View style={styles.list}>
        {alternatives.map((alternative, index) => (
          <AlternativeRow key={alternative.id} alternative={alternative} rank={index + 2} />
        ))}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.surfaceContainerLow, gap: 4 },
  subtitle: { marginBottom: 8 },
  list: { gap: 4 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.outlineVariant,
  },
  rank: {
    width: 26,
    height: 26,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceContainerHighest,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowText: { flex: 1, gap: 1 },
  rowMetrics: { alignItems: 'flex-end', gap: 1 },
});
