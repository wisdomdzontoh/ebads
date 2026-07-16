/** API client transport contract (docs/04, docs/12 §8) — builds requests, parses, and errors. */

import { ApiClient, ApiError } from '../api';

const OK = (body: unknown): Response =>
  ({ ok: true, status: 200, statusText: 'OK', text: async () => JSON.stringify(body) }) as Response;

const FAIL = (status: number, body: unknown): Response =>
  ({ ok: false, status, statusText: 'ERR', text: async () => JSON.stringify(body) }) as Response;

describe('ApiClient', () => {
  const fetchMock = jest.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it('fetches facilities from the versioned base URL', async () => {
    fetchMock.mockResolvedValueOnce(OK([{ id: 'f-1' }]));
    const client = new ApiClient({ baseUrl: 'http://host:8000/api/v1/' });
    const facilities = await client.getFacilities();

    expect(facilities).toEqual([{ id: 'f-1' }]);
    // Trailing slash on the base URL is trimmed; path is appended.
    expect(fetchMock).toHaveBeenCalledWith('http://host:8000/api/v1/facilities', expect.any(Object));
  });

  it('sends the API key header when configured', async () => {
    fetchMock.mockResolvedValueOnce(OK({ status: 'allocated' }));
    const client = new ApiClient({ baseUrl: 'http://host/api/v1', apiKey: 'secret' });
    await client.createAllocation({
      patient_lat: 5.6,
      patient_lon: -0.18,
      urgency: 'critical',
      required_bed_type: 'icu',
    });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>)['X-API-Key']).toBe('secret');
  });

  it('throws ApiError with the HTTP status on a non-2xx response', async () => {
    fetchMock.mockResolvedValueOnce(FAIL(404, { detail: 'simulation session not found' }));
    const client = new ApiClient({ baseUrl: 'http://host/api/v1' });
    await expect(client.getSimulationSession('missing')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: 'simulation session not found',
    });
  });

  it('surfaces a network failure as ApiError status 0', async () => {
    fetchMock.mockRejectedValueOnce(new Error('Network request failed'));
    const client = new ApiClient({ baseUrl: 'http://host/api/v1' });
    await expect(client.getFacilities()).rejects.toBeInstanceOf(ApiError);
    await expect(client.getFacilities()).rejects.toMatchObject({ status: 0 });
  });
});
