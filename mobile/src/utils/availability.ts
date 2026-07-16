/**
 * Availability presentation helpers (docs/05 §2.2).
 *
 * Maps a facility's cached bed counts onto a display tone (colour). This is PRESENTATION only
 * — a count → colour lookup for the map/list. It does not score, filter, or rank facilities for
 * allocation; that is the engine's job (docs/05 §8). The list is shown in the cache's order,
 * never re-sorted by availability.
 */

import type { BedCount, BedType } from '../services/types';
import { colors } from '../theme';

// Display-only threshold: at or below this many free beds a facility reads as "low" (amber).
const LOW_THRESHOLD = 3;

export type AvailabilityTone = 'none' | 'low' | 'ok';

/** Total free beds across all bed types (the map/list badge number). */
export function totalAvailable(bedCounts: BedCount[]): number {
  return bedCounts.reduce((sum, bed) => sum + bed.available, 0);
}

/** Map a free-bed total onto a triage-style availability tone. */
export function availabilityTone(total: number): AvailabilityTone {
  if (total <= 0) return 'none';
  if (total <= LOW_THRESHOLD) return 'low';
  return 'ok';
}

export const TONE_COLOR: Record<AvailabilityTone, string> = {
  none: colors.criticalRed,
  low: colors.urgentOrange,
  ok: colors.standardGreen,
};

export const TONE_TINT: Record<AvailabilityTone, string> = {
  none: colors.redTint,
  low: colors.orangeTint,
  ok: colors.greenTint,
};

/** Google Static Maps marker colour names, keyed by tone. */
export const TONE_STATIC_COLOR: Record<AvailabilityTone, string> = {
  none: 'red',
  low: 'orange',
  ok: 'green',
};

const BED_SHORT: Record<BedType, string> = {
  general: 'GEN',
  icu: 'ICU',
  maternity_specialist: 'MAT',
};

/** A compact per-bed-type availability summary, e.g. "GEN 14 · ICU 2 · MAT 8". */
export function bedSummary(bedCounts: BedCount[]): string {
  return bedCounts.map((bed) => `${BED_SHORT[bed.bed_type]} ${bed.available}`).join(' · ');
}
