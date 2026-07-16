/**
 * Simulation setup options (docs/05 §2.3). The algorithm + occupancy choices the dispatcher
 * picks before creating a session; these are submitted to `POST /simulation/sessions` and the
 * engine does all the work. Defaults mirror the study parameters (docs/09).
 */

import type { AlgorithmName } from '../../services/types';

export const ALGORITHM_OPTIONS: { value: AlgorithmName; label: string }[] = [
  { value: 'greedy', label: 'Greedy' },
  { value: 'weighted', label: 'Weighted' },
  { value: 'urgency_adaptive', label: 'Urgency-Adaptive' },
];

export const OCCUPANCY_OPTIONS: number[] = [0.75, 0.9, 1.0];

export const DEFAULT_EVENTS = 100;
export const DEFAULT_SEED = 20260617;

/** Format a possibly-null metric mean: null (undefined mean) reads as an em dash, never 0. */
export function formatMetric(value: number | null, digits = 1): string {
  return value === null ? '—' : value.toFixed(digits);
}
