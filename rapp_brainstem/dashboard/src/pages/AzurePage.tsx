import {
  makeStyles,
  tokens,
  Text,
  Spinner,
  Button,
  Subtitle1,
  Tree,
  TreeItem,
  TreeItemLayout,
  Badge,
} from '@fluentui/react-components';
import { ArrowClockwise24Regular } from '@fluentui/react-icons';
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
  costRow: {
    display: 'flex',
    gap: '24px',
    padding: '16px',
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: tokens.borderRadiusMedium,
  },
  costItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  costValue: {
    fontSize: '24px',
    fontWeight: '700',
  },
});

interface PageProps {
  data: DashboardData | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function AzurePage({ data, loading, error: _error, onRefresh }: PageProps) {
  const styles = useStyles();

  if (loading && !data) {
    return <Spinner label="Loading Azure resources..." size="large" />;
  }

  if (!data) return null;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <Subtitle1>Azure</Subtitle1>
        <Button
          appearance="subtle"
          icon={<ArrowClockwise24Regular />}
          onClick={onRefresh}
          disabled={loading}
        />
      </div>

      {/* Cost Summary */}
      <div className={styles.costRow}>
        <div className={styles.costItem}>
          <Text size={200} className={styles.costValue} style={{ color: tokens.colorPaletteGreenForeground1 }}>
            ${data.azure.cost.actual.toFixed(2)}
          </Text>
          <Text size={200}>Actual Cost (MTD)</Text>
        </div>
        <div className={styles.costItem}>
          <Text size={200} className={styles.costValue}>
            ${data.azure.cost.forecast.toFixed(2)}
          </Text>
          <Text size={200}>Forecasted Cost</Text>
        </div>
        <div className={styles.costItem}>
          <Text size={200} className={styles.costValue}>
            {data.azure.totalResources}
          </Text>
          <Text size={200}>Total Resources</Text>
        </div>
      </div>

      {/* Resource Groups Tree */}
      <div>
        <Text weight="semibold" size={400} style={{ marginBottom: 12, display: 'block' }}>
          Resource Groups
        </Text>
        <Tree aria-label="Resource groups">
          {data.azure.resourceGroups.map(rg => (
            <TreeItem key={rg.name} itemType="branch">
              <TreeItemLayout>
                <Text weight="semibold">{rg.name}</Text>
                <Badge appearance="tint" size="small" style={{ marginLeft: 8 }}>
                  {rg.resources.length} resources
                </Badge>
                <Text size={100} style={{ marginLeft: 8 }}>
                  ({rg.location})
                </Text>
              </TreeItemLayout>
              <Tree>
                {rg.resources.map(res => (
                  <TreeItem key={`${rg.name}-${res.name}`} itemType="leaf">
                    <TreeItemLayout>
                      <Text size={200}>{res.name}</Text>
                      <Text size={100} style={{ marginLeft: 8, color: tokens.colorNeutralForeground3 }}>
                        {res.type.split('/').pop()}
                      </Text>
                    </TreeItemLayout>
                  </TreeItem>
                ))}
              </Tree>
            </TreeItem>
          ))}
        </Tree>
      </div>
    </div>
  );
}
