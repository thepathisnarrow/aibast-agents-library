import { useEffect, useRef, useState } from 'react';
import {
  makeStyles,
  tokens,
  Text,
  Badge,
  Spinner,
  Button,
  Tooltip,
} from '@fluentui/react-components';
import {
  Bot24Regular,
  Person24Regular,
  Wrench20Regular,
  CheckmarkCircle20Filled,
  ErrorCircle20Filled,
  QuestionCircle20Filled,
  ChatHelp20Regular,
  Dismiss20Regular,
} from '@fluentui/react-icons';
import type { RunEvent, RunState, RunStatus } from '../api/types';
import { fetchRunEvents, cancelRun } from '../api/client';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    marginTop: '12px',
    padding: '12px',
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingBottom: '6px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  scroll: {
    maxHeight: '420px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    paddingRight: '6px',
    scrollbarWidth: 'thin',
  },
  event: {
    display: 'flex',
    gap: '8px',
    padding: '8px 10px',
    borderRadius: tokens.borderRadiusSmall,
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  eventIcon: {
    flexShrink: 0,
    marginTop: '2px',
  },
  eventBody: {
    flex: 1,
    minWidth: 0,
  },
  eventMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    marginBottom: '2px',
  },
  eventText: {
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    fontFamily: tokens.fontFamilyBase,
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground1,
  },
  toolBox: {
    backgroundColor: tokens.colorNeutralBackground2,
    border: `1px solid ${tokens.colorNeutralStroke3}`,
    borderRadius: tokens.borderRadiusSmall,
    padding: '6px 8px',
    fontFamily: tokens.fontFamilyMonospace,
    fontSize: '11px',
    marginTop: '4px',
    maxHeight: '180px',
    overflowY: 'auto',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  summary: {
    marginTop: '8px',
    padding: '10px',
    borderRadius: tokens.borderRadiusSmall,
    backgroundColor: tokens.colorPaletteGreenBackground2,
    border: `1px solid ${tokens.colorPaletteGreenBorder2}`,
    whiteSpace: 'pre-wrap',
  },
  error: {
    marginTop: '8px',
    padding: '10px',
    borderRadius: tokens.borderRadiusSmall,
    backgroundColor: tokens.colorPaletteRedBackground2,
    border: `1px solid ${tokens.colorPaletteRedBorder2}`,
    whiteSpace: 'pre-wrap',
  },
});

interface Props {
  run: RunState;
  /** Optional callback when the run reaches a terminal state. */
  onTerminal?: (state: RunStatus) => void;
}

const POLL_ACTIVE_MS = 1500;
const POLL_IDLE_MS = 5000;

export function RunTranscript({ run, onTerminal }: Props) {
  const styles = useStyles();
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [status, setStatus] = useState<RunStatus>(run.status);
  const sinceRef = useRef<number>(-1);
  const scrollRef = useRef<HTMLDivElement>(null);
  const terminalNotifiedRef = useRef(false);

  // Poll for events
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      if (cancelled) return;
      try {
        const resp = await fetchRunEvents(run.run_id, sinceRef.current);
        if (cancelled) return;
        if (resp.events.length > 0) {
          sinceRef.current = resp.next_since;
          setEvents(prev => [...prev, ...resp.events]);
        }
        if (resp.status) setStatus(resp.status);

        const terminal =
          resp.status === 'completed' ||
          resp.status === 'failed' ||
          resp.status === 'cancelled';
        if (terminal && !terminalNotifiedRef.current) {
          terminalNotifiedRef.current = true;
          onTerminal?.(resp.status!);
        }

        const interval =
          resp.status === 'running' || resp.status === 'awaiting_user'
            ? POLL_ACTIVE_MS
            : terminal
              ? 0 // stop polling
              : POLL_IDLE_MS;
        if (interval > 0) {
          timer = setTimeout(tick, interval);
        }
      } catch {
        timer = setTimeout(tick, POLL_IDLE_MS);
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [run.run_id, onTerminal]);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events.length]);

  const statusColor = (s: RunStatus) => {
    switch (s) {
      case 'completed': return 'success' as const;
      case 'failed': return 'danger' as const;
      case 'cancelled': return 'subtle' as const;
      case 'awaiting_user': return 'warning' as const;
      default: return 'informative' as const;
    }
  };

  const isActive = status === 'running' || status === 'awaiting_user' || status === 'queued';

  // Pull out summary if present
  const completedEvent = events.find(
    e => e.type === 'run_completed' || e.type === 'run_failed',
  );
  const summary = (completedEvent?.data as { summary?: string } | undefined)?.summary;

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          {isActive && <Spinner size="tiny" />}
          <Text weight="semibold" size={300}>Run transcript</Text>
          <Badge appearance="filled" color={statusColor(status)} size="small">
            {status}
          </Badge>
          <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
            {run.run_id} · {events.length} events
          </Text>
        </div>
        {isActive && (
          <Tooltip content="Cancel run" relationship="label">
            <Button
              size="small"
              appearance="subtle"
              icon={<Dismiss20Regular />}
              onClick={() => cancelRun(run.run_id)}
            />
          </Tooltip>
        )}
      </div>

      <div className={styles.scroll} ref={scrollRef}>
        {events.length === 0 && (
          <Text size={200} italic style={{ color: tokens.colorNeutralForeground3, padding: '8px' }}>
            Waiting for events...
          </Text>
        )}
        {events.map(ev => (
          <EventRow key={ev.seq} event={ev} />
        ))}
      </div>

      {summary && status === 'completed' && (
        <div className={styles.summary}>
          <Text weight="semibold" size={200}>✓ Completed</Text>
          <div className={styles.eventText} style={{ marginTop: 4 }}>{summary}</div>
        </div>
      )}
      {summary && status === 'failed' && (
        <div className={styles.error}>
          <Text weight="semibold" size={200}>✗ Failed</Text>
          <div className={styles.eventText} style={{ marginTop: 4 }}>{summary}</div>
        </div>
      )}
    </div>
  );
}

// ── Individual event renderer ───────────────────────────────────────────────

function EventRow({ event }: { event: RunEvent }) {
  const styles = useStyles();
  const data = event.data as Record<string, unknown>;
  const ts = new Date(event.ts).toLocaleTimeString();

  switch (event.type) {
    case 'run_queued':
    case 'run_started':
    case 'round_started':
    case 'run_completed':
    case 'run_failed':
    case 'run_cancelled': {
      const label =
        event.type === 'round_started'
          ? `Round ${data.round}`
          : event.type.replace(/_/g, ' ');
      return (
        <div className={styles.event} style={{ opacity: 0.7 }}>
          <div className={styles.eventBody}>
            <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
              {ts} · {label}
            </Text>
          </div>
        </div>
      );
    }

    case 'llm_message': {
      const role = String(data.role || 'assistant');
      const content = String(data.content || '');
      const Icon = role === 'user' ? Person24Regular : Bot24Regular;
      return (
        <div className={styles.event}>
          <div className={styles.eventIcon}>
            <Icon />
          </div>
          <div className={styles.eventBody}>
            <div className={styles.eventMeta}>
              <Text weight="semibold" size={200}>{role}</Text>
              <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>{ts}</Text>
            </div>
            <div className={styles.eventText}>{content}</div>
          </div>
        </div>
      );
    }

    case 'tool_call': {
      const name = String(data.name || '?');
      const args = JSON.stringify(data.arguments || {}, null, 2);
      return (
        <div className={styles.event}>
          <div className={styles.eventIcon}>
            <Wrench20Regular />
          </div>
          <div className={styles.eventBody}>
            <div className={styles.eventMeta}>
              <Text weight="semibold" size={200}>→ {name}</Text>
              <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>{ts}</Text>
            </div>
            <div className={styles.toolBox}>{args}</div>
          </div>
        </div>
      );
    }

    case 'tool_result': {
      const name = String(data.name || '?');
      const ok = data.ok !== false;
      const result = String(data.result || '');
      const Icon = ok ? CheckmarkCircle20Filled : ErrorCircle20Filled;
      const color = ok ? tokens.colorPaletteGreenForeground1 : tokens.colorPaletteRedForeground1;
      return (
        <div className={styles.event}>
          <div className={styles.eventIcon} style={{ color }}>
            <Icon />
          </div>
          <div className={styles.eventBody}>
            <div className={styles.eventMeta}>
              <Text weight="semibold" size={200}>← {name}</Text>
              <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>{ts}</Text>
            </div>
            <div className={styles.toolBox}>{result}</div>
          </div>
        </div>
      );
    }

    case 'question': {
      return (
        <div className={styles.event} style={{ borderColor: tokens.colorPaletteYellowBorder2 }}>
          <div className={styles.eventIcon} style={{ color: tokens.colorPaletteYellowForeground1 }}>
            <QuestionCircle20Filled />
          </div>
          <div className={styles.eventBody}>
            <div className={styles.eventMeta}>
              <Text weight="semibold" size={200}>Asked user</Text>
              <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>{ts}</Text>
            </div>
            <div className={styles.eventText}>{String(data.question || '')}</div>
            {data.context ? (
              <div className={styles.eventText} style={{ color: tokens.colorNeutralForeground3, marginTop: 4 }}>
                Context: {String(data.context)}
              </div>
            ) : null}
          </div>
        </div>
      );
    }

    case 'answer': {
      return (
        <div className={styles.event}>
          <div className={styles.eventIcon}>
            <ChatHelp20Regular />
          </div>
          <div className={styles.eventBody}>
            <div className={styles.eventMeta}>
              <Text weight="semibold" size={200}>User answered</Text>
              <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>{ts}</Text>
            </div>
            <div className={styles.eventText}>{String(data.answer || '')}</div>
          </div>
        </div>
      );
    }

    default:
      return null;
  }
}
