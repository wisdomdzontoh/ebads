/**
 * Guard test — the client must contain NO matching logic (docs/05 §8, docs/12 §8).
 *
 * The thesis boundary (docs/05 §3, §8) is that all scoring, filtering, and ranking happen in
 * the engine; the app only renders the engine's response. This test scans the client source for
 * (a) the engine's internal algorithm identifiers and (b) any `.sort(` call — both of which
 * would signal that matching (or ranking) had leaked into the client. It is a review-blocking
 * violation if this fails.
 *
 * Rendering engine-provided fields (score, weight_vector, capability_match, t_hat…) is allowed;
 * COMPUTING or RE-ORDERING them is not, which is exactly what the forbidden tokens below detect.
 */

import { readdirSync, readFileSync, statSync } from 'fs';
import { join } from 'path';

// Engine-internal matching identifiers that must never appear client-side, plus `.sort(`
// (the client never ranks/orders candidates — order comes from the engine or the cache query).
const FORBIDDEN: RegExp[] = [
  /min_max|minMax/,
  /weighted_score|weightedScore/,
  /\bargmin\b/,
  /hard_filter|hardFilter/,
  /RADIUS_MINUTES/,
  /CAPABILITY_MATRIX/,
  /ALGORITHM_2_WEIGHTS|ALGORITHM_3_WEIGHTS/,
  /select_algorithm|selectAlgorithm/,
  /normalize\s*\(/,
  /\.sort\s*\(/,
];

const SRC_DIR = join(__dirname, '..');

function sourceFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry === '__tests__') continue; // don't scan the guard's own forbidden-token list
      files.push(...sourceFiles(full));
    } else if (/\.(ts|tsx)$/.test(entry)) {
      files.push(full);
    }
  }
  return files;
}

describe('no client-side matching logic', () => {
  it('contains no engine algorithm internals or candidate re-ordering', () => {
    const offenders: string[] = [];
    for (const file of sourceFiles(SRC_DIR)) {
      const contents = readFileSync(file, 'utf8');
      for (const pattern of FORBIDDEN) {
        if (pattern.test(contents)) {
          offenders.push(`${file} matches ${pattern}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});
