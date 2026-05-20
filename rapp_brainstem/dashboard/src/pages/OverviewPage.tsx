import {
  makeStyles,
  tokens,
  Card,
  CardHeader,
  Text,
  Spinner,
  Button,
  Subtitle1,
  Tooltip,
} from '@fluentui/react-components';
import { ArrowClockwise24Regular, Open16Regular, Play16Regular, Pause16Regular, Warning16Regular, ErrorCircle16Regular } from '@fluentui/react-icons';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import type { DashboardData } from '../api/types';
import { capacityAction } from '../api/client';

const AZURE_PORTAL_URL = 'https://portal.azure.com/#@MngEnvMCAP874580.onmicrosoft.com/resource/subscriptions/4342cec8-495e-4192-bbd3-cad9d93facc9/overview';
const FABRIC_PORTAL_URL = 'https://app.fabric.microsoft.com/';
const PURVIEW_PORTAL_URL = 'https://purview.microsoft.com/';

// Budget thresholds (match Azure tab defaults)
const BUDGET = 2000;
const WARNING_PCT = 25;
const ACTION_PCT = 10;

function getCostColor(totalCost: number): string {
  const warningThreshold = BUDGET * (1 - WARNING_PCT / 100);
  const actionThreshold = BUDGET * (1 - ACTION_PCT / 100);
  if (totalCost >= actionThreshold) return tokens.colorPaletteRedForeground1;
  if (totalCost >= warningThreshold) return tokens.colorPaletteYellowForeground1;
  return tokens.colorPaletteGreenForeground1;
}

const useStyles = makeStyles({
  page: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '16px',
  },
  card: {
    cursor: 'pointer',
    transition: 'box-shadow 0.2s',
    ':hover': {
      boxShadow: tokens.shadow8,
    },
  },
  cardHeaderRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
  },
  statValue: {
    fontSize: '32px',
    fontWeight: '700',
    lineHeight: '1.2',
  },
  statLabel: {
    color: tokens.colorNeutralForeground3,
    fontSize: '12px',
    textAlign: 'right' as const,
  },
  statRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    padding: '8px 0',
  },
  capacityRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '8px 0',
  },
  capacityDot: {
    width: '16px',
    height: '16px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  capacityDotActive: {
    backgroundColor: tokens.colorPaletteGreenBackground3,
  },
  capacityDotInactive: {
    backgroundColor: tokens.colorPaletteRedBackground3,
  },
  errorCard: {
    backgroundColor: tokens.colorPaletteRedBackground1,
    color: tokens.colorPaletteRedForeground1,
    padding: '16px',
    borderRadius: tokens.borderRadiusMedium,
  },
  spinning: {
    animationName: {
      from: { transform: 'rotate(0deg)' },
      to: { transform: 'rotate(360deg)' },
    },
    animationDuration: '1s',
    animationIterationCount: 'infinite',
    animationTimingFunction: 'linear',
  },
  portalLink: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '12px',
    color: tokens.colorBrandForeground1,
    textDecoration: 'none',
    ':hover': {
      textDecoration: 'underline',
    },
  },
  shimmer: {
    display: 'inline-block',
    width: '80px',
    height: '32px',
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground4,
    animationName: {
      '0%': { opacity: 0.4 },
      '50%': { opacity: 0.8 },
      '100%': { opacity: 0.4 },
    },
    animationDuration: '1.5s',
    animationIterationCount: 'infinite',
    animationTimingFunction: 'ease-in-out',
  },
});

interface PageProps {
  data: DashboardData | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function OverviewPage({ data, loading, error, onRefresh }: PageProps) {
  const styles = useStyles();
  const navigate = useNavigate();
  const [capStatus, setCapStatus] = useState<Record<string, { type: 'warning' | 'error'; message: string } | null>>({});
  const [capLoading, setCapLoading] = useState<Record<string, boolean>>({});

  if (error) {
    return (
      <div className={styles.page}>
        <div className={styles.errorCard}>
          <Text weight="semibold">Error: </Text>
          <Text>{error}</Text>
          <Button appearance="primary" icon={<ArrowClockwise24Regular />} onClick={onRefresh} style={{ marginLeft: 16 }}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (loading && !data) {
    return <Spinner label="Loading dashboard..." size="large" />;
  }

  if (!data) return null;

  const activeProjects = data.agents.projects.filter(p => p.status === 'in-progress');
  const demosInQueue = data.demos.filter(d => d.status !== 'completed');

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <Subtitle1>Environment Overview</Subtitle1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Button
            appearance="subtle"
            icon={<ArrowClockwise24Regular className={loading ? styles.spinning : undefined} />}
            onClick={onRefresh}
            disabled={loading}
          >
            Refresh
          </Button>
        </div>
      </div>

      <div className={styles.grid}>
        {/* Agents Card */}
        <Card className={styles.card} onClick={() => navigate('/agents')}>
          <CardHeader header={<Text weight="semibold">Agents</Text>} />
          <div style={{ padding: '0 16px 16px' }}>
            <div className={styles.statRow}>
              <span className={styles.statValue}>{data.agents.loaded.length}</span>
              <span className={styles.statLabel}>Agents Online</span>
            </div>
            <div className={styles.statRow}>
              <span className={styles.statValue}>{demosInQueue.length}</span>
              <span className={styles.statLabel}>In Queue</span>
            </div>
            {activeProjects.length > 0 && (
              <Text size={200} truncate>
                Working: {activeProjects[0].title}
              </Text>
            )}
          </div>
        </Card>

        {/* Azure Card */}
        <Card className={styles.card} onClick={() => navigate('/azure')}>
          <CardHeader header={
            <div className={styles.cardHeaderRow}>
              <Text weight="semibold">Azure</Text>
              <a
                href={AZURE_PORTAL_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.portalLink}
                onClick={(e) => e.stopPropagation()}
              >
                <Open16Regular /> Portal
              </a>
            </div>
          } />
          <div style={{ padding: '0 16px 16px' }}>
            <div className={styles.statRow}>
              {loading && (data.azure.cost.actual || data.azure.cost.forecast) && (
                <ArrowClockwise24Regular className={styles.spinning} style={{ fontSize: 16 }} />
              )}
              {(!data.azure.cost.actual && !data.azure.cost.forecast) ? (
                <Spinner size="tiny" />
              ) : (
                <span className={styles.statValue} style={{ color: getCostColor(data.azure.cost.actual + data.azure.cost.forecast) }}>
                  ${(data.azure.cost.actual + data.azure.cost.forecast).toFixed(2)}
                </span>
              )}
              <span className={styles.statLabel} style={{ flex: 1 }}>Forecasted Cost</span>
            </div>
            <div className={styles.statRow}>
              <span className={styles.statValue}>{data.azure.totalResources}</span>
              <span className={styles.statLabel}>Resources</span>
            </div>
          </div>
        </Card>

        {/* Fabric Card */}
        <Card className={styles.card} onClick={() => navigate('/fabric')}>
          <CardHeader header={
            <div className={styles.cardHeaderRow}>
              <Text weight="semibold">Fabric</Text>
              <a
                href={FABRIC_PORTAL_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.portalLink}
                onClick={(e) => e.stopPropagation()}
              >
                <Open16Regular /> Portal
              </a>
            </div>
          } />
          <div style={{ padding: '0 16px 16px' }}>
            {data.fabric.capacities.map(cap => (
              <div key={cap.id} className={styles.capacityRow}>
                {(loading || capLoading[cap.id]) && (
                  <ArrowClockwise24Regular className={styles.spinning} style={{ fontSize: 14 }} />
                )}
                <span className={`${styles.capacityDot} ${cap.state === 'Active' ? styles.capacityDotActive : styles.capacityDotInactive}`} />
                {!(loading || capLoading[cap.id]) && (cap.state === 'Active' ? (
                  <Tooltip content="Click to take the capacity offline (Pause)" relationship="label">
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={<Pause16Regular style={{ color: tokens.colorPaletteRedForeground1 }} />}
                      onClick={(e) => {
                        e.stopPropagation();
                        setCapLoading(s => ({ ...s, [cap.id]: true }));
                        setCapStatus(s => ({ ...s, [cap.id]: null }));
                        capacityAction(cap.resourceId, 'suspend').then(result => {
                          if (result.status === 'succeeded') {
                            setCapStatus(s => ({ ...s, [cap.id]: null }));
                          } else {
                            setCapStatus(s => ({ ...s, [cap.id]: { type: result.status as 'warning' | 'error', message: result.message || 'Unknown issue' } }));
                          }
                          setCapLoading(s => ({ ...s, [cap.id]: false }));
                          onRefresh();
                        });
                      }}
                    />
                  </Tooltip>
                ) : (
                  <Tooltip content="Click to bring the capacity online (Resume)" relationship="label">
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={<Play16Regular style={{ color: tokens.colorPaletteGreenForeground1 }} />}
                      onClick={(e) => {
                        e.stopPropagation();
                        setCapLoading(s => ({ ...s, [cap.id]: true }));
                        setCapStatus(s => ({ ...s, [cap.id]: null }));
                        capacityAction(cap.resourceId, 'resume').then(result => {
                          if (result.status === 'succeeded') {
                            setCapStatus(s => ({ ...s, [cap.id]: null }));
                          } else {
                            setCapStatus(s => ({ ...s, [cap.id]: { type: result.status as 'warning' | 'error', message: result.message || 'Unknown issue' } }));
                          }
                          setCapLoading(s => ({ ...s, [cap.id]: false }));
                          onRefresh();
                        });
                      }}
                    />
                  </Tooltip>
                ))}
                {capStatus[cap.id]?.type === 'warning' && (
                  <Warning16Regular style={{ color: tokens.colorPaletteYellowForeground1 }} title={capStatus[cap.id]!.message} />
                )}
                {capStatus[cap.id]?.type === 'error' && (
                  <ErrorCircle16Regular style={{ color: tokens.colorPaletteRedForeground1 }} title={capStatus[cap.id]!.message} />
                )}
                <span className={styles.statLabel} style={{ flex: 1, textAlign: 'right' }}>{cap.name} — {cap.state}</span>
              </div>
            ))}
            <div className={styles.statRow}>
              <span className={styles.statValue}>{data.fabric.workspaces.length}</span>
              <span className={styles.statLabel}>Workspaces</span>
            </div>
          </div>
        </Card>

        {/* Purview Card */}
        <Card className={styles.card} onClick={() => navigate('/purview')}>
          <CardHeader header={
            <div className={styles.cardHeaderRow}>
              <Text weight="semibold">Purview</Text>
              <a
                href={PURVIEW_PORTAL_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.portalLink}
                onClick={(e) => e.stopPropagation()}
              >
                <Open16Regular /> Portal
              </a>
            </div>
          } />
          <div style={{ padding: '0 16px 16px' }}>
            <div className={styles.statRow}>
              <span className={styles.statValue}>{data.purview.assets.count}</span>
              <span className={styles.statLabel}>Data Assets</span>
            </div>
            <div className={styles.statRow}>
              <span className={styles.statValue}>{data.purview.policies.count}</span>
              <span className={styles.statLabel}>Policies</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
