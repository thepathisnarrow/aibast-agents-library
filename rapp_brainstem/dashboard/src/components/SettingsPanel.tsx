import { useState, useEffect } from 'react';
import {
  DrawerBody,
  DrawerHeader,
  DrawerHeaderTitle,
  OverlayDrawer,
  makeStyles,
  tokens,
  Text,
  Badge,
  Divider,
  Spinner,
  Input,
  Button,
  Switch,
} from '@fluentui/react-components';
import {
  Dismiss24Regular,
  PersonKey24Regular,
  ShieldCheckmark20Regular,
  ShieldDismiss20Regular,
  Add20Regular,
  Delete20Regular,
  Save20Regular,
  ChevronRight20Regular,
  ChevronDown20Regular,
} from '@fluentui/react-icons';
import type { AuthAccount } from '../api/types';
import { fetchAuthConfig, saveAuthConfig } from '../api/client';

const useStyles = makeStyles({
  section: {
    marginBottom: '24px',
  },
  sectionTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '12px',
  },
  accountCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '12px',
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
    marginBottom: '12px',
  },
  accountHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    cursor: 'pointer',
    userSelect: 'none',
  },
  accountHeaderLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  fieldRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  label: {
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase200,
  },
  actions: {
    display: 'flex',
    gap: '8px',
    marginTop: '12px',
    justifyContent: 'flex-end',
  },
  statusMsg: {
    marginTop: '8px',
    fontSize: tokens.fontSizeBase200,
  },
});

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const styles = useStyles();
  const [accounts, setAccounts] = useState<AuthAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [originalAccounts, setOriginalAccounts] = useState<AuthAccount[]>([]);

  const isDirty = JSON.stringify(accounts) !== JSON.stringify(originalAccounts);

  useEffect(() => {
    if (open) {
      setLoading(true);
      setStatusMsg('');
      fetchAuthConfig()
        .then((cfg) => { setAccounts(cfg.accounts); setOriginalAccounts(cfg.accounts); })
        .catch(() => { setAccounts([]); setOriginalAccounts([]); })
        .finally(() => setLoading(false));
    }
  }, [open]);

  const updateAccount = (index: number, field: keyof AuthAccount, value: string | boolean) => {
    setAccounts((prev) => prev.map((a, i) => i === index ? { ...a, [field]: value } : a));
  };

  const addAccount = () => {
    const newKey = `tenant_${Date.now()}`;
    setAccounts((prev) => [
      ...prev,
      { key: newKey, username: '', domain: '', displayName: '', adminAccess: false, isPrimary: false },
    ]);
    setExpanded((prev) => ({ ...prev, [newKey]: true }));
  };

  const removeAccount = (index: number) => {
    setAccounts((prev) => prev.filter((_, i) => i !== index));
  };

  const setPrimary = (index: number) => {
    setAccounts((prev) =>
      prev.map((a, i) => ({ ...a, isPrimary: i === index }))
    );
  };

  const handleSave = async () => {
    setSaving(true);
    setStatusMsg('');
    try {
      await saveAuthConfig(accounts);
      setOriginalAccounts(accounts);
      setStatusMsg('Saved successfully.');
    } catch (e: unknown) {
      setStatusMsg(`Error: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <OverlayDrawer open={open} onOpenChange={(_, { open: isOpen }) => { if (!isOpen) onClose(); }} position="end" size="medium">
      <DrawerHeader>
        <DrawerHeaderTitle
          action={
            <button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}>
              <Dismiss24Regular />
            </button>
          }
        >
          Settings
        </DrawerHeaderTitle>
      </DrawerHeader>
      <DrawerBody>
        <div className={styles.section}>
          <div className={styles.sectionTitle}>
            <PersonKey24Regular />
            <Text weight="semibold" size={400}>Authentication</Text>
          </div>
          <Divider style={{ marginBottom: '12px' }} />

          {loading && <Spinner size="small" label="Loading accounts..." />}

          {!loading && accounts.map((account, idx) => (
            <div key={account.key} className={styles.accountCard}>
              <div className={styles.accountHeader} onClick={() => setExpanded((prev) => ({ ...prev, [account.key]: !prev[account.key] }))}>
                <div className={styles.accountHeaderLeft}>
                  {expanded[account.key] ? <ChevronDown20Regular /> : <ChevronRight20Regular />}
                  <Text weight="semibold">{account.displayName || account.key || 'Untitled'}</Text>
                  {account.isPrimary && (
                    <Badge appearance="filled" color="brand" size="small">Primary</Badge>
                  )}
                  <Badge
                    appearance="filled"
                    color={account.adminAccess ? 'success' : 'informative'}
                    icon={account.adminAccess ? <ShieldCheckmark20Regular /> : <ShieldDismiss20Regular />}
                    size="small"
                  >
                    {account.adminAccess ? 'Admin' : 'Read-only'}
                  </Badge>
                </div>
                <Button
                  appearance="subtle"
                  icon={<Delete20Regular />}
                  size="small"
                  onClick={(e) => { e.stopPropagation(); removeAccount(idx); }}
                  title="Remove account"
                />
              </div>
              {expanded[account.key] && (
                <>
                  <div className={styles.fieldRow}>
                    <Text className={styles.label}>Display Name</Text>
                    <Input
                      size="small"
                      value={account.displayName}
                      onChange={(_, d) => updateAccount(idx, 'displayName', d.value)}
                      placeholder="e.g. MCAPS Primary"
                    />
                  </div>
                  <div className={styles.fieldRow}>
                    <Text className={styles.label}>Username / Login</Text>
                    <Input
                      size="small"
                      value={account.username}
                      onChange={(_, d) => updateAccount(idx, 'username', d.value)}
                      placeholder="e.g. user@domain.com"
                    />
                  </div>
                  <div className={styles.fieldRow}>
                    <Text className={styles.label}>Domain / Tenant ID</Text>
                    <Input
                      size="small"
                      value={account.domain}
                      onChange={(_, d) => updateAccount(idx, 'domain', d.value)}
                      placeholder="e.g. contoso.onmicrosoft.com or GUID"
                    />
                  </div>
                  <Switch
                    label={account.isPrimary ? 'Primary — used for all default operations' : 'Not primary'}
                    checked={account.isPrimary}
                    onChange={() => setPrimary(idx)}
                  />
                  <Switch
                    label={account.adminAccess ? 'Admin — service status will be fetched' : 'Not Admin — service status skipped'}
                    checked={account.adminAccess}
                    onChange={(_, d) => updateAccount(idx, 'adminAccess', d.checked)}
                  />
                </>
              )}
            </div>
          ))}

          {!loading && (
            <>
              <Button appearance="outline" icon={<Add20Regular />} onClick={addAccount}>
                Add Account
              </Button>

              <div className={styles.actions}>
                {!isDirty && statusMsg && (
                  <Text className={styles.statusMsg} style={{ color: statusMsg.startsWith('Error') ? tokens.colorPaletteRedForeground1 : tokens.colorPaletteGreenForeground1 }}>
                    {statusMsg}
                  </Text>
                )}
                {isDirty && (
                  <Button appearance="primary" icon={<Save20Regular />} onClick={handleSave} disabled={saving}>
                    {saving ? 'Saving...' : 'Save'}
                  </Button>
                )}
              </div>
            </>
          )}
        </div>
      </DrawerBody>
    </OverlayDrawer>
  );
}
