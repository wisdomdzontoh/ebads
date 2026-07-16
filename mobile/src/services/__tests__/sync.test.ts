/** Sync behaviour (docs/05 §5, docs/12 §8) — best-effort, never a silent success. */

import type { ApiClient } from '../api';
import { getSyncMeta, saveFacilities, setSyncMeta } from '../cache';
import { runSync } from '../sync';
import type { Facility } from '../types';

jest.mock('../cache');

const mockedSave = saveFacilities as jest.MockedFunction<typeof saveFacilities>;
const mockedSetMeta = setSyncMeta as jest.MockedFunction<typeof setSyncMeta>;
const mockedGetMeta = getSyncMeta as jest.MockedFunction<typeof getSyncMeta>;

const FACILITY = { id: 'f-1' } as Facility;

function apiReturning(facilities: Facility[] | Error): ApiClient {
  return {
    getFacilities: jest.fn(async () => {
      if (facilities instanceof Error) throw facilities;
      return facilities;
    }),
  } as unknown as ApiClient;
}

beforeEach(() => jest.clearAllMocks());

describe('runSync', () => {
  it('saves facilities and records success', async () => {
    const outcome = await runSync(apiReturning([FACILITY]));
    expect(outcome).toMatchObject({ ok: true, count: 1 });
    expect(mockedSave).toHaveBeenCalledWith([FACILITY], expect.any(String));
    expect(mockedSetMeta).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'success', facility_count: 1 }),
    );
  });

  it('on failure keeps the previous timestamp and marks the sync failed (never silent)', async () => {
    mockedGetMeta.mockResolvedValueOnce({
      last_sync_at: '2026-07-02T09:00:00Z',
      status: 'success',
      facility_count: 24,
    });
    const outcome = await runSync(apiReturning(new Error('offline')));
    expect(outcome).toMatchObject({ ok: false, lastSyncAt: '2026-07-02T09:00:00Z' });
    expect(mockedSave).not.toHaveBeenCalled();
    expect(mockedSetMeta).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'failed', last_sync_at: '2026-07-02T09:00:00Z' }),
    );
  });
});
