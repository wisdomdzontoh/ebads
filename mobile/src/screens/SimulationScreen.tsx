/**
 * Simulation screen (docs/05 §2.3) — demonstration + audit surface, not daily dispatch.
 *
 * Creates a session and either runs it automatically (returning the ATBP/FRR/MCEE/CM metrics)
 * or steps through it interactively (returning the per-event decision trace). All computation
 * happens in the engine via `/simulation/...`; this screen configures, submits, and renders.
 * Requires connectivity — offline it shows a note (the engine is unreachable).
 */

import React, { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText, InlineNotice, Screen } from '../components';
import { ApiError } from '../services/api';
import { loadFacilities } from '../services/cache';
import type {
  RunSummary,
  SimulationSessionCreate,
  SimulationSessionRead,
  StepTrace,
} from '../services/types';
import { useConnectivity } from '../state/ConnectivityContext';
import { useSettings } from '../state/SettingsContext';
import { RunSummaryView } from './simulation/RunSummaryView';
import { SetupCard } from './simulation/SetupCard';
import { StepTraceView } from './simulation/StepTraceView';

type Mode = 'setup' | 'auto' | 'interactive';

export function SimulationScreen(): React.ReactElement {
  const { api, connection } = useSettings();
  const { online } = useConnectivity();
  const [mode, setMode] = useState<Mode>('setup');
  const [session, setSession] = useState<SimulationSessionRead | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [trace, setTrace] = useState<StepTrace | null>(null);
  const [busy, setBusy] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [facilityNames, setFacilityNames] = useState<Record<string, string>>({});

  // Facility id → name map (from the cache), so the step trace can label candidates. A cache
  // failure only means candidates show short ids instead of names — never a crash.
  useEffect(() => {
    void loadFacilities()
      .then((facilities) => {
        setFacilityNames(Object.fromEntries(facilities.map((f) => [f.id, f.name])));
      })
      .catch(() => setFacilityNames({}));
  }, []);

  const fail = (err: unknown): void => {
    // Shown inline on the screen (Alert.alert is a silent no-op on web).
    setError(err instanceof ApiError ? err.message : 'Could not reach the engine.');
  };

  const reset = (): void => {
    setMode('setup');
    setSession(null);
    setSummary(null);
    setTrace(null);
    setComplete(false);
    setError(null);
  };

  const runAutomatic = async (config: SimulationSessionCreate): Promise<void> => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createSimulationSession(config);
      const result = await api.runSimulation(created.id);
      setSession(created);
      setSummary(result);
      setMode('auto');
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  };

  const startInteractive = async (config: SimulationSessionCreate): Promise<void> => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createSimulationSession(config);
      const first = await api.stepSimulation(created.id);
      setSession(created);
      setTrace(first);
      setComplete(first.event_index + 1 >= created.events_planned);
      setMode('interactive');
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  };

  const stepNext = async (): Promise<void> => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.stepSimulation(session.id);
      setTrace(next);
      setComplete(next.event_index + 1 >= session.events_planned);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setComplete(true); // session already finished
      } else {
        fail(error);
      }
    } finally {
      setBusy(false);
    }
  };

  if (!online) {
    return (
      <Screen title="Simulation">
        <AppText variant="bodyLg" color="onSurfaceVariant">
          Simulation runs on the engine and needs connectivity. Reconnect to run or step a
          session.
        </AppText>
      </Screen>
    );
  }

  return (
    <Screen title="Simulation">
      {mode === 'setup' ? (
        <View style={styles.intro}>
          <AppText variant="headlineLg" color="slate900">
            Simulation
          </AppText>
          <AppText variant="bodySm" color="onSurfaceVariant">
            Configure a session, then run it automatically or step through decisions.
          </AppText>
        </View>
      ) : null}

      {connection.status === 'failed' ? (
        <InlineNotice
          tone="info"
          title="Engine connection failed its last test"
          message="Verify the base URL and API key in Settings before running a simulation."
        />
      ) : null}

      {error ? <InlineNotice title="Simulation failed" message={error} /> : null}

      {mode === 'setup' ? (
        <SetupCard loading={busy} onRun={runAutomatic} onStep={startInteractive} />
      ) : null}

      {mode === 'auto' && summary && session ? (
        <RunSummaryView summary={summary} session={session} onReset={reset} />
      ) : null}

      {mode === 'interactive' && trace && session ? (
        <StepTraceView
          trace={trace}
          session={session}
          facilityNames={facilityNames}
          stepping={busy}
          complete={complete}
          onStep={() => void stepNext()}
          onReset={reset}
        />
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  intro: { gap: 4 },
});
