import {
  makeStyles,
  tokens,
  Text,
  Spinner,
  Button,
  Subtitle1,
  Card,
  CardHeader,
  Link,
} from '@fluentui/react-components';
import { ArrowClockwise24Regular, Open16Regular } from '@fluentui/react-icons';
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
  assetBreakdown: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    paddingTop: '8px',
  },
  assetRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '4px 8px',
    borderRadius: tokens.borderRadiusSmall,
    backgroundColor: tokens.colorNeutralBackground3,
  },
});

interface PageProps {
  data: DashboardData | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function PurviewPage({ data, loading, error: _error, onRefresh }: PageProps) {
  const styles = useStyles();

  if (loading && !data) {
    return <Spinner label="Loading Purview data..." size="large" />;
  }

  if (!data) return null;

  const purviewUrl = 'https://purview.microsoft.com';

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Subtitle1>Purview</Subtitle1>
          <Link
            href={purviewUrl}
            target="_blank"
            style={{ display: 'flex', alignItems: 'center', gap: 4 }}
          >
            Open Purview <Open16Regular />
          </Link>
        </div>
        <Button
          appearance="subtle"
          icon={<ArrowClockwise24Regular />}
          onClick={onRefresh}
          disabled={loading}
        />
      </div>

      <div className={styles.grid}>
        {/* Catalog Assets */}
        <Card>
          <CardHeader header={<Text weight="semibold">Catalog Assets</Text>} />
          <div style={{ padding: '0 16px 16px' }}>
            <div className={styles.statRow}>
              <span className={styles.statValue}>{data.purview.assets.count}</span>
              <span className={styles.statLabel}>Total Assets</span>
            </div>
            {Object.keys(data.purview.assets.byType).length > 0 && (
              <div className={styles.assetBreakdown}>
                {Object.entries(data.purview.assets.byType).map(([type, count]) => (
                  <div key={type} className={styles.assetRow}>
                    <Text size={200}>{type}</Text>
                    <Text size={200} weight="semibold">{count}</Text>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Policies */}
        <Card>
          <CardHeader header={<Text weight="semibold">Policies</Text>} />
          <div style={{ padding: '0 16px 16px' }}>
            <div className={styles.statRow}>
              <span className={styles.statValue}>{data.purview.policies.count}</span>
              <span className={styles.statLabel}>Active Policies</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
