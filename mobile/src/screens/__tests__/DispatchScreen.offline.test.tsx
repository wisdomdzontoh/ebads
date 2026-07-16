/**
 * Offline boundary test (docs/05 §3, docs/12 §8).
 *
 * The review-critical behaviour: when offline, the Dispatch tab renders the read-only cached
 * facilities + the "matching requires connectivity" banner, and issues NO allocation request.
 * We mock connectivity as offline and the engine client, render the screen, and assert the
 * informational view appears and `createAllocation` is never called.
 *
 * Uses react-test-renderer directly (the RNTL renderer is not wired for this RN/React combo).
 */

import React from 'react';
import TestRenderer, { act } from 'react-test-renderer';

// Engine client — the name is `mock*`-prefixed so the jest.mock factory may reference it.
const mockApi = { createAllocation: jest.fn() };

jest.mock('../../state/ConnectivityContext', () => ({
  useConnectivity: () => ({ online: false }),
}));

jest.mock('../../state/SettingsContext', () => ({
  useSettings: () => ({
    api: mockApi,
    settings: { baseUrl: '', apiKey: '', syncIntervalMinutes: 15, pushEnabled: true },
    ready: true,
    connection: { status: 'untested', message: null, checkedAt: null, facilityCount: null },
    update: jest.fn(),
    setConnection: jest.fn(),
  }),
}));

jest.mock('../../state/SyncContext', () => ({
  useSync: () => ({
    lastSync: { last_sync_at: '2026-07-03T09:00:00Z', status: 'success', facility_count: 1 },
    syncing: false,
    lastError: null,
    syncNow: jest.fn(),
  }),
}));

jest.mock('../../services/cache', () => ({
  loadFacilities: jest.fn(async () => [
    {
      id: 'f1',
      name: '37 Military Hospital',
      tier: 'tertiary',
      latitude: 5.58,
      longitude: -0.18,
      contact_phone: '+233000000000',
      supported_bed_types: ['icu'],
      bed_counts: [{ bed_type: 'icu', available: 2, capacity: 12, updated_at: '' }],
      synced_at: '2026-07-03T09:00:00Z',
    },
  ]),
}));

import { DispatchScreen } from '../DispatchScreen';

describe('DispatchScreen offline mode', () => {
  beforeEach(() => mockApi.createAllocation.mockClear());

  it('renders cached facilities + banner and issues no allocation request', async () => {
    let tree!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      tree = TestRenderer.create(<DispatchScreen />);
    });
    // Flush the loadFacilities() promise + its state update.
    await act(async () => {
      await Promise.resolve();
    });

    const rendered = JSON.stringify(tree.toJSON());

    // The informational view: banner, the read-only cached facility, and the disabled note.
    expect(rendered).toContain('Matching requires connectivity');
    expect(rendered).toContain('37 Military Hospital');
    expect(rendered).toContain('dispatch disabled until online');
    // The dispatch form CTA is not rendered offline.
    expect(rendered).not.toContain('Find nearest bed');

    // The strict boundary: no allocation request was issued while offline.
    expect(mockApi.createAllocation).not.toHaveBeenCalled();
  });
});
