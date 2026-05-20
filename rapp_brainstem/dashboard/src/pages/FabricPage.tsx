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
import { ArrowClockwise24Regular, Open16Regular, Play16Regular, Pause16Regular, Warning16Regular, ErrorCircle16Regular } from '@fluentui/react-icons';
import { useState } from 'react';
import type { DashboardData } from '../api/types';
import { capacityAction } from '../api/client';

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
  const [capStatus, setCapStatus] = useState<Record<string, { type: 'warning' | 'error'; message: string } | null>>({});
  const [capLoading, setCapLoading] = useState<Record<string, boolean>>({});

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
          const isActive = cap.state === 'Active';
          const capWorkspaces = data.fabric.workspaces.filter(
            ws => ws.capacityId === cap.id
          );
          return (
            <TreeItem key={cap.id} itemType={isActive ? 'branch' : 'leaf'}>
              <TreeItemLayout>
                <div className={styles.capacityHeader}>
                  <Badge
                    appearance="filled"
                    color={isActive ? 'success' : 'danger'}
                    size="small"
                  />
                  {capLoading[cap.id] ? (
                    <Spinner size="tiny" />
                  ) : isActive ? (
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
                      title="Pause capacity"
                    />
                  ) : (
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
                      title="Resume capacity"
                    />
                  )}
                  {capStatus[cap.id]?.type === 'warning' && (
                    <Warning16Regular style={{ color: tokens.colorPaletteYellowForeground1 }} title={capStatus[cap.id]!.message} />
                  )}
                  {capStatus[cap.id]?.type === 'error' && (
                    <ErrorCircle16Regular style={{ color: tokens.colorPaletteRedForeground1 }} title={capStatus[cap.id]!.message} />
                  )}
                  <Text weight="semibold">{cap.name}</Text>
                  <Badge appearance="tint" size="small">
                    {cap.sku}
                  </Badge>
                  <Text size={100}>({cap.region})</Text>
                  {!isActive && (
                    <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>— {cap.state}</Text>
                  )}
                </div>
              </TreeItemLayout>
              {isActive && (
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
              )}
            </TreeItem>
          );
        })}
      </Tree>
    </div>
  );
}
