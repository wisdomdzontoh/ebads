/**
 * Regression test for the CONFIRMED-vs-ALLOCATED status mismatch (see `services/types.ts`'s
 * `AllocatedResponse` docstring): the engine's live `/allocations` response uses
 * `status: "confirmed"` (backend/app/parameters.py::AllocationStatus.CONFIRMED), not
 * `"allocated"` — a client that checks for the wrong literal renders EVERY successful
 * placement as an escalation. Drives the actual form (GPS → urgency → bed type → submit) so
 * this exercises the same branch a real dispatch does, not just the type declaration.
 *
 * Uses react-test-renderer directly (the RNTL renderer is not wired for this RN/React combo) —
 * same approach as `DispatchScreen.offline.test.tsx`.
 */

import React from 'react';
import TestRenderer, { act } from 'react-test-renderer';

const mockCreateAllocation = jest.fn(async () => ({
  id: 'alloc-1',
  status: 'confirmed',
  recommended_facility: {
    id: 'f-1',
    name: 'Korle Bu Teaching Hospital',
    tier: 'tertiary',
    available_beds: 5,
    travel_time_minutes: 12.3,
    is_estimated_travel_time: false,
    latitude: 5.5366,
    longitude: -0.2261,
    contact_phone: '+233302739401',
  },
  algorithm_used: 'urgency_adaptive',
  weight_vector: { w_t: 0.5, w_b: 0.1, w_c: 0.4 },
  capability_match: 1.0,
  candidates_evaluated: 3,
  attempts: 1,
  eta_minutes: 12.3,
  selection_reason: 'Lowest urgency-adaptive score among 3 reachable facilities.',
  ranked_alternatives: [
    {
      id: 'f-2',
      name: 'Ridge Hospital',
      tier: 'tertiary',
      available_beds: 2,
      travel_time_minutes: 18.1,
      is_estimated_travel_time: false,
      capability_match: 1.0,
      score: 0.42,
    },
  ],
}));

const mockApi = {
  createAllocation: mockCreateAllocation,
  // Resolved (not bare jest.fn()) so the screen's 20s revocation-poll interval — real timers,
  // still pending after the test's own assertions run — has something to .then() rather than
  // throwing into the test process during teardown if it fires before unmount() cancels it.
  getAllocation: jest.fn(async () => ({ status: 'confirmed', revocation_reason: null })),
  recordArrival: jest.fn(),
  reallocate: jest.fn(),
};

jest.mock('../../state/ConnectivityContext', () => ({
  useConnectivity: () => ({ online: true }),
}));

jest.mock('../../state/AuthContext', () => ({
  useAuth: () => ({
    session: { accessToken: 't', refreshToken: 'r', role: 'dispatcher', facilityId: null, email: 'd@example.com' },
    ready: true,
    api: mockApi,
    login: jest.fn(),
    logout: jest.fn(),
    changePassword: jest.fn(),
  }),
}));

jest.mock('../../state/SettingsContext', () => ({
  useSettings: () => ({
    settings: { syncIntervalMinutes: 15, pushEnabled: false, onboarded: true },
    ready: true,
    // 'ok' so ConnectionHint (which needs react-navigation context) never renders.
    connection: { status: 'ok', message: null, checkedAt: null },
    update: jest.fn(),
    setConnection: jest.fn(),
  }),
}));

import { DispatchScreen } from '../DispatchScreen';

function pressByLabel(tree: TestRenderer.ReactTestRenderer, label: string): void {
  // Match by prop, not component type — `findAllByType(Pressable)` can miss matches when the
  // test file's `Pressable` import resolves to a different module instance than the one the
  // screen under test uses (an RN/jest-expo module-resolution quirk, not a real absence).
  const matches = tree.root.findAll(
    (n) => n.props && n.props.accessibilityLabel === label && typeof n.props.onPress === 'function',
  );
  if (matches.length === 0) throw new Error(`No pressable with accessibilityLabel "${label}"`);
  act(() => {
    matches[0].props.onPress();
  });
}

describe('DispatchScreen — confirmed allocation renders the recommendation, not an escalation', () => {
  beforeEach(() => mockCreateAllocation.mockClear());

  it('shows "Bed allocated", never "Manual decision required", for a confirmed response', async () => {
    let tree!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      tree = TestRenderer.create(<DispatchScreen />);
    });

    pressByLabel(tree, 'Use GPS to set the patient location');
    await act(async () => {
      await Promise.resolve();
    });

    pressByLabel(tree, 'Critical urgency, R 30 min');
    pressByLabel(tree, 'ICU bed');
    pressByLabel(tree, 'Find nearest bed');

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockCreateAllocation).toHaveBeenCalledTimes(1);

    const rendered = JSON.stringify(tree.toJSON());
    expect(rendered).toContain('Bed allocated');
    expect(rendered).toContain('Korle Bu Teaching Hospital');
    expect(rendered).not.toContain('Manual decision required');
    // Ranked alternatives render below the recommendation (RecommendationCard's own docstring).
    expect(rendered).toContain('Ranked alternatives');
    expect(rendered).toContain('Ridge Hospital');

    // Unmount so the revocation-poll interval's cleanup (clearInterval) actually runs — real
    // timers, otherwise a 20s-later poll would fire into a torn-down test process.
    act(() => {
      tree.unmount();
    });
  });
});
