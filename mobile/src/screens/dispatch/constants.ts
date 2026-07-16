/**
 * Dispatch form metadata — display labels + semantic colours for the triage and bed-type
 * selectors (docs/05 §2.1, DESIGN.md §Triage Selectors).
 *
 * The urgency radius labels ("R 30 min" …) mirror the engine's documented radii (docs/09 §2)
 * purely as INFORMATION for the dispatcher. They are never used to filter or match — the
 * engine owns all matching (docs/05 §8). Nothing here computes a decision.
 */

import { colors } from '../../theme';
import type { BedType, Urgency } from '../../services/types';

export interface UrgencyMeta {
  value: Urgency;
  label: string;
  radiusLabel: string;
  color: string;
  tint: string;
}

export const URGENCY_META: UrgencyMeta[] = [
  {
    value: 'critical',
    label: 'Critical',
    radiusLabel: 'R 30 min',
    color: colors.criticalRed,
    tint: colors.redTint,
  },
  {
    value: 'urgent',
    label: 'Urgent',
    radiusLabel: 'R 60 min',
    color: colors.urgentOrange,
    tint: colors.orangeTint,
  },
  {
    value: 'standard',
    label: 'Standard',
    radiusLabel: 'R 90 min',
    color: colors.standardGreen,
    tint: colors.greenTint,
  },
];

export interface BedTypeMeta {
  value: BedType;
  label: string;
}

export const BED_TYPE_META: BedTypeMeta[] = [
  { value: 'general', label: 'General' },
  { value: 'icu', label: 'ICU' },
  { value: 'maternity_specialist', label: 'Maternity' },
];

/** Human labels for a facility tier, shown on recommendation/escalation cards. */
export const TIER_LABEL: Record<string, string> = {
  tertiary: 'Tertiary Facility',
  secondary: 'Secondary Facility',
  primary: 'Primary Facility',
};
