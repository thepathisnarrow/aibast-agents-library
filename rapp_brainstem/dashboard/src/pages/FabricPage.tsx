import {
  makeStyles,
  tokens,
  Text,
  Spinner,
  Button,
  Subtitle1,
  Badge,
  Tree,
  TreeItem,
  TreeItemLayout,
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
  capacityHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
});

interface PageProps {
  data: DashboardData | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function FabricPage({ data, loading, error: _error, onRefresh }: PageProps) {
  const styles = useStyles();

  if (loading && !data) {
    return <Spinner label="Loading Fabric data..." size="large" />;
  }

  if (!data) return null;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Subtitle1>Fabric</Subtitle1>
          <Link
            href="https://app.fabric.microsoft.com"
            target="_blank"
            style={{ display: 'flex', alignItems: 'center', gap: 4 }}
          >
            Open Fabric <Open16Regular />
          </Link>
        </div>
        <Button
          appearance="subtle"
          icon={<ArrowClockwise24Regular />}
          onClick={onRefresh}
          disabled={loading}
        />
      </div>

      {/* Capacities → Workspaces → Items tree */}
      <Tree aria-label="Fabric capacities">
        {data.fabric.capacities.map(cap => {
          const capWorkspaces = data.fabric.workspaces.filter(
            ws => ws.capacityId === cap.id
          );
          return (
            <TreeItem key={cap.id} itemType="branch">
              <TreeItemLayout>
                <div className={styles.capacityHeader}>
                  <Badge
                    appearance="filled"
                    color={cap.state === 'Active' ? 'success' : 'danger'}
                    size="small"
                  />
                  <Text weight="semibold">{cap.name}</Text>
                  <Badge appearance="tint" size="small">
                    {cap.sku}
                  </Badge>
                  <Text size={100}>({cap.region})</Text>
                </div>
              </TreeItemLayout>
              <Tree>
                {capWorkspaces.map(ws => (
                  <TreeItem key={ws.id} itemType={ws.items && ws.items.length > 0 ? 'branch' : 'leaf'}>
                    <TreeItemLayout>
                      <Text>{ws.name}</Text>
                      <Badge appearance="tint" size="small" style={{ marginLeft: 8 }}>
                        {ws.type}
                      </Badge>
                    </TreeItemLayout>
                    {ws.items && ws.items.length > 0 && (
                      <Tree>
                        {ws.items.map(item => (
                          <TreeItem key={item.id} itemType="leaf">
                            <TreeItemLayout>
                              <Text size={200}>{item.displayName}</Text>
                              <Text
                                size={100}
                                style={{ marginLeft: 8, color: tokens.colorNeutralForeground3 }}
                              >
                                {item.type}
                              </Text>
                            </TreeItemLayout>
                          </TreeItem>
                        ))}
                      </Tree>
                    )}
                  </TreeItem>
                ))}
                {capWorkspaces.length === 0 && (
                  <TreeItem itemType="leaf">
                    <TreeItemLayout>
                      <Text size={200} italic>No workspaces assigned</Text>
                    </TreeItemLayout>
                  </TreeItem>
                )}
              </Tree>
            </TreeItem>
          );
        })}
      </Tree>
    </div>
  );
}
