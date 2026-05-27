import { useEffect, useState, useCallback } from 'react';
import {
  Button,
  Tooltip,
  Text,
  Badge,
  tokens,
  makeStyles,
} from '@fluentui/react-components';
import { Play20Filled, History20Regular } from '@fluentui/react-icons';
import type { RunState } from '../api/types';
import { fetchRunsForDemo, startDemoRun } from '../api/client';
import { RunTranscript } from './RunTranscript';

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  history: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    color: tokens.colorNeutralForeground3,
    cursor: 'pointer',
    userSelect: 'none',
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    marginTop: '8px',
  },
});

interface Props {
  demoId: string;
}

export function DemoRunSection({ demoId }: Props) {
  const styles = useStyles();
  const [runs, setRuns] = useState<RunState[]>([]);
  const [starting, setStarting] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const list = await fetchRunsForDemo(demoId);
    setRuns(list);
  }, [demoId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const activeRun = runs.find(
    r => r.status === 'running' || r.status === 'awaiting_user' || r.status === 'queued',
  );
  const latestTerminal = runs.find(
    r => r.status === 'completed' || r.status === 'failed' || r.status === 'cancelled',
  );
  const visibleRun = activeRun || latestTerminal;

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      const state = await startDemoRun(demoId);
      setRuns(prev => [state, ...prev.filter(r => r.run_id !== state.run_id)]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start run');
    } finally {
      setStarting(false);
    }
  };

  return (
    <>
      <div className={styles.controls}>
        <Tooltip
          content={activeRun ? 'A run is already in progress' : 'Run this demo end-to-end'}
          relationship="label"
        >
          <Button
            appearance="primary"
            size="small"
            icon={<Play20Filled />}
            onClick={handleStart}
            disabled={starting || !!activeRun}
          >
            {activeRun ? 'Running…' : starting ? 'Starting…' : 'Run demo'}
          </Button>
        </Tooltip>
        {runs.length > 1 && (
          <Tooltip
            content={showHistory ? 'Hide previous runs' : `Show all ${runs.length} runs`}
            relationship="label"
          >
            <Button
              appearance="subtle"
              size="small"
              icon={<History20Regular />}
              onClick={() => setShowHistory(s => !s)}
            >
              {runs.length}
            </Button>
          </Tooltip>
        )}
      </div>

      {error && (
        <Text size={200} style={{ color: tokens.colorPaletteRedForeground1, marginTop: 6 }}>
          {error}
        </Text>
      )}

      {visibleRun && !showHistory && (
        <RunTranscript run={visibleRun} onTerminal={() => refresh()} />
      )}

      {showHistory && (
        <div className={styles.list}>
          {runs.map(run => (
            <div key={run.run_id}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', margin: '8px 0 4px' }}>
                <Badge appearance="outline" size="small">
                  {new Date(run.started_at || run.updated_at).toLocaleString()}
                </Badge>
                <Badge
                  appearance="filled"
                  size="small"
                  color={
                    run.status === 'completed' ? 'success'
                    : run.status === 'failed' ? 'danger'
                    : run.status === 'cancelled' ? 'subtle'
                    : run.status === 'awaiting_user' ? 'warning'
                    : 'informative'
                  }
                >
                  {run.status}
                </Badge>
              </div>
              <RunTranscript run={run} onTerminal={() => refresh()} />
            </div>
          ))}
        </div>
      )}
    </>
  );
}
