/** Cache serialization round-trip (docs/12 §8) — pure helpers, no native SQLite needed. */

import { fromRow, toRow } from '../cache';
import type { Facility } from '../types';

const FACILITY: Facility = {
  id: 'f-1',
  name: '37 Military Hospital',
  latitude: 5.5826,
  longitude: -0.188,
  tier: 'tertiary',
  supported_bed_types: ['general', 'icu', 'maternity_specialist'],
  contact_phone: '+233000000000',
  active_data_source: 'simulation',
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
  bed_counts: [{ bed_type: 'icu', available: 2, capacity: 12, updated_at: '2026-07-01T00:00:00Z' }],
};

describe('cache serialization', () => {
  it('round-trips a facility through row form', () => {
    const cached = fromRow(toRow(FACILITY, '2026-07-02T09:00:00Z'));
    expect(cached.id).toBe('f-1');
    expect(cached.name).toBe('37 Military Hospital');
    expect(cached.tier).toBe('tertiary');
    expect(cached.supported_bed_types).toEqual(['general', 'icu', 'maternity_specialist']);
    expect(cached.bed_counts).toHaveLength(1);
    expect(cached.bed_counts[0]).toMatchObject({ bed_type: 'icu', available: 2, capacity: 12 });
    expect(cached.synced_at).toBe('2026-07-02T09:00:00Z');
  });

  it('stores array fields as JSON strings in the row', () => {
    const row = toRow(FACILITY, '2026-07-02T09:00:00Z');
    expect(typeof row.supported_bed_types).toBe('string');
    expect(JSON.parse(row.supported_bed_types)).toEqual(FACILITY.supported_bed_types);
  });
});
