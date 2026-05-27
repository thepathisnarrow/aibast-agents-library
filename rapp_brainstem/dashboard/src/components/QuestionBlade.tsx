import { useEffect, useState } from 'react';
import {
  OverlayDrawer,
  DrawerHeader,
  DrawerHeaderTitle,
  DrawerBody,
  Button,
  Textarea,
  Text,
  Badge,
  tokens,
  makeStyles,
  Spinner,
} from '@fluentui/react-components';
import { Dismiss24Regular, Send20Filled } from '@fluentui/react-icons';
import type { RunState } from '../api/types';
import { fetchAwaitingUserRuns, answerRunQuestion } from '../api/client';
import { RunTranscript } from './RunTranscript';

const useStyles = makeStyles({
  drawer: {
    width: 'min(640px, 95vw)',
  },
  question: {
    padding: '14px',
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorPaletteYellowBackground2,
    border: `1px solid ${tokens.colorPaletteYellowBorder2}`,
    marginBottom: '14px',
  },
  questionLabel: {
    marginBottom: '6px',
    display: 'block',
  },
  questionText: {
    whiteSpace: 'pre-wrap',
    fontSize: tokens.fontSizeBase400,
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground1,
  },
  context: {
    marginTop: '8px',
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground3,
    whiteSpace: 'pre-wrap',
  },
  answerRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    marginBottom: '14px',
  },
  meta: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
    marginBottom: '10px',
  },
  emptyHint: {
    padding: '16px',
    textAlign: 'center',
    color: tokens.colorNeutralForeground3,
  },
});

const POLL_INTERVAL_MS = 3000;

/**
 * Global blade that auto-opens whenever an agent run is awaiting a user answer.
 * Mount once near the root of the app.
 */
export function QuestionBlade() {
  const styles = useStyles();
  const [awaitingRuns, setAwaitingRuns] = useState<RunState[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [answer, setAnswer] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  // Poll for runs awaiting user input
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const runs = await fetchAwaitingUserRuns();
        if (cancelled) return;
        setAwaitingRuns(runs);
        // Auto-pick the first non-dismissed run as active
        const next = runs.find(r => !dismissedIds.has(r.run_id));
        setActiveRunId(prev => {
          if (prev && runs.some(r => r.run_id === prev)) return prev;
          return next?.run_id ?? null;
        });
      } catch {
        /* ignore */
      }
    };
    poll();
    const t = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [dismissedIds]);

  const activeRun = awaitingRuns.find(r => r.run_id === activeRunId) || null;
  const isOpen = !!activeRun;

  // Reset textarea when active run changes
  useEffect(() => {
    setAnswer('');
    setError(null);
  }, [activeRunId]);

  const handleClose = () => {
    if (activeRun) {
      setDismissedIds(prev => new Set(prev).add(activeRun.run_id));
    }
    setActiveRunId(null);
  };

  const handleSubmit = async () => {
    if (!activeRun?.pending_question || !answer.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await answerRunQuestion(
        activeRun.run_id,
        activeRun.pending_question.question_id,
        answer.trim(),
      );
      // Clear dismissed list for this run (the run will move out of awaiting_user)
      setDismissedIds(prev => {
        const next = new Set(prev);
        next.delete(activeRun.run_id);
        return next;
      });
      setActiveRunId(null);
      setAnswer('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit answer');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <OverlayDrawer
      position="end"
      open={isOpen}
      onOpenChange={(_, { open }) => { if (!open) handleClose(); }}
      className={styles.drawer}
    >
      <DrawerHeader>
        <DrawerHeaderTitle
          action={
            <Button
              appearance="subtle"
              aria-label="Close"
              icon={<Dismiss24Regular />}
              onClick={handleClose}
            />
          }
        >
          Agent needs your input
        </DrawerHeaderTitle>
      </DrawerHeader>
      <DrawerBody>
        {!activeRun ? (
          <div className={styles.emptyHint}>No pending questions.</div>
        ) : (
          <>
            <div className={styles.meta}>
              <Text weight="semibold" size={400}>{activeRun.demo_title}</Text>
              <Badge appearance="filled" color="warning" size="small">
                awaiting answer
              </Badge>
              {awaitingRuns.length > 1 && (
                <Badge appearance="outline" size="small">
                  +{awaitingRuns.length - 1} more
                </Badge>
              )}
            </div>

            {activeRun.pending_question && (
              <div className={styles.question}>
                <Text size={200} weight="semibold" className={styles.questionLabel}>
                  Question
                </Text>
                <div className={styles.questionText}>
                  {activeRun.pending_question.question}
                </div>
                {activeRun.pending_question.context && (
                  <div className={styles.context}>
                    {activeRun.pending_question.context}
                  </div>
                )}
              </div>
            )}

            <div className={styles.answerRow}>
              <Text size={200} weight="semibold">Your answer</Text>
              <Textarea
                value={answer}
                onChange={(_, data) => setAnswer(data.value)}
                placeholder="Type your answer..."
                rows={4}
                disabled={submitting}
              />
              {error && (
                <Text size={200} style={{ color: tokens.colorPaletteRedForeground1 }}>
                  {error}
                </Text>
              )}
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <Button appearance="secondary" onClick={handleClose} disabled={submitting}>
                  Later
                </Button>
                <Button
                  appearance="primary"
                  icon={submitting ? <Spinner size="tiny" /> : <Send20Filled />}
                  onClick={handleSubmit}
                  disabled={!answer.trim() || submitting}
                >
                  Send answer
                </Button>
              </div>
            </div>

            <RunTranscript run={activeRun} />
          </>
        )}
      </DrawerBody>
    </OverlayDrawer>
  );
}
