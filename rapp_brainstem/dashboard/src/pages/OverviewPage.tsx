import {
  makeStyles,
  tokens,
  Card,
  CardHeader,
  Text,
  Badge,
  Spinner,
  Button,
  Subtitle1,
} from '@fluentui/react-components';
import { ArrowClockwise24Regular } from '@fluentui/react-icons';
import { useNavigate } from 'react-router-dom';
import type { DashboardData } from '../api/types';

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
  statValue: {
    fontSize: '32px',
    fontWeight: '700',
    lineHeight: '1.2',
  },
  statLabel: {
    color: tokens.colorNeutralForeground3,
    fontSize: '12px',
  },
  statRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    padding: '8px 0',
  },
  capacityRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '4px 0',
  },
  errorCard: {
    backgroundColor: tokens.colorPaletteRedBackground1,
    color: tokens.colorPaletteRedForeground1,
    padding: '16px',
    borderRadius: tokens.borderRadiusMedium,
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
  const queuedProjects = data.agents.projects.filter(p => p.status === 'queued');

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <Subtitle1>Environment Overview</Subtitle1>
        <Button
          appearance="subtle"
          icon={<ArrowClockwise24Regular />}
          onClick={onRefresh}
          disabled={loading}
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </Button>
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
              <span className={styles.statValue}>{queuedProjects.length}</span>
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
          <CardHeader header={<Text weight="semibold">Azure</Text>} />
          <div style={{ padding: '0 16px 16px' }}>
            <div className={styles.statRow}>
              <span className={styles.statValue}>{data.azure.totalResources}</span>
              <span className={styles.statLabel}>Resources</span>
            </div>
            <div className={styles.statRow}>
              <Text size={300}>
                Actual: <Text weight="semibold">${data.azure.cost.actual.toFixed(2)}</Text>
              </Text>
            </div>
            <div className={styles.statRow}>
              <Text size={300}>
                Forecast: <Text weight="semibold">${data.azure.cost.forecast.toFixed(2)}</Text>
              </Text>
            </div>
          </div>
        </Card>

        {/* Fabric Card */}
        <Card className={styles.card} onClick={() => navigate('/fabric')}>
          <CardHeader header={<Text weight="semibold">Fabric</Text>} />
          <div style={{ padding: '0 16px 16px' }}>
            {data.fabric.capacities.map(cap => (
              <div key={cap.id} className={styles.capacityRow}>
                <Badge
                  appearance="filled"
                  color={cap.state === 'Active' ? 'success' : 'danger'}
                  size="small"
                />
                <Text size={200}>{cap.name}</Text>
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
          <CardHeader header={<Text weight="semibold">Purview</Text>} />
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
