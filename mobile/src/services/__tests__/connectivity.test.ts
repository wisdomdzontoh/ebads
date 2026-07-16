/** Connectivity reduction (docs/05 §3, docs/12 §8) — the online/offline gate logic. */

import type { NetInfoState } from '@react-native-community/netinfo';

import { isStateOnline } from '../connectivity';

function state(partial: Partial<NetInfoState>): NetInfoState {
  return { type: 'wifi', ...partial } as NetInfoState;
}

describe('isStateOnline', () => {
  it('is online when connected and internet reachable', () => {
    expect(isStateOnline(state({ isConnected: true, isInternetReachable: true }))).toBe(true);
  });

  it('is online when reachability is unknown (null) but connected', () => {
    expect(isStateOnline(state({ isConnected: true, isInternetReachable: null }))).toBe(true);
  });

  it('is offline when connected but internet is explicitly unreachable', () => {
    expect(isStateOnline(state({ isConnected: true, isInternetReachable: false }))).toBe(false);
  });

  it('is offline when not connected', () => {
    expect(isStateOnline(state({ isConnected: false, isInternetReachable: false }))).toBe(false);
  });
});
