import { ReactNode, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  makeStyles,
  tokens,
  TabList,
  Tab,
  Switch,
  Text,
  Tooltip,
  Select,
  Button,
} from '@fluentui/react-components';
import {
  BrainCircuit24Regular,
  Home24Regular,
  Bot24Regular,
  Cloud24Regular,
  Database24Regular,
  Shield24Regular,
  Beaker24Regular,
  WeatherMoon24Regular,
  WeatherSunny24Regular,
  ArrowSync24Regular,
  Settings24Regular,
} from '@fluentui/react-icons';
import { SettingsPanel } from './SettingsPanel';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    minHeight: '100vh',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 24px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  nav: {
    display: 'flex',
    alignItems: 'center',
  },
  themeToggle: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  controls: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  refreshControl: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  content: {
    flex: 1,
    padding: '24px',
    overflow: 'auto',
  },
});

interface ShellProps {
  children: ReactNode;
  isDark: boolean;
  onToggleTheme: () => void;
  refreshInterval: number;
  onRefreshIntervalChange: (ms: number) => void;
}

const tabs = [
  { value: '/', label: 'Overview', icon: <Home24Regular /> },
  { value: '/agents', label: 'Agents', icon: <Bot24Regular /> },
  { value: '/demos', label: 'Demos', icon: <Beaker24Regular /> },
  { value: '/azure', label: 'Azure', icon: <Cloud24Regular /> },
  { value: '/fabric', label: 'Fabric', icon: <Database24Regular /> },
  { value: '/purview', label: 'Purview', icon: <Shield24Regular /> },
];

export function Shell({ children, isDark, onToggleTheme, refreshInterval, onRefreshIntervalChange }: ShellProps) {
  const styles = useStyles();
  const navigate = useNavigate();
  const location = useLocation();
  const [settingsOpen, setSettingsOpen] = useState(false);

  const currentTab = tabs.find(t => t.value === location.pathname)?.value ?? '/';

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <BrainCircuit24Regular />
          <Text weight="semibold" size={500}>
            Brainstem
          </Text>
        </div>

        <nav className={styles.nav}>
          <TabList
            selectedValue={currentTab}
            onTabSelect={(_, d) => navigate(d.value as string)}
            size="medium"
          >
            {tabs.map(tab => (
              <Tab key={tab.value} value={tab.value} icon={tab.icon}>
                {tab.label}
              </Tab>
            ))}
          </TabList>
        </nav>

        <div className={styles.controls}>
          <div className={styles.refreshControl}>
            <ArrowSync24Regular />
            <Select
              size="small"
              value={String(refreshInterval)}
              onChange={(_, d) => onRefreshIntervalChange(Number(d.value))}
            >
              <option value="10000">10s</option>
              <option value="30000">30s</option>
              <option value="60000">1 min</option>
              <option value="300000">5 min</option>
              <option value="0">Off</option>
            </Select>
          </div>

          <div className={styles.themeToggle}>
            <Tooltip content={isDark ? 'Switch to light mode' : 'Switch to dark mode'} relationship="label">
              <Switch
                checked={isDark}
                onChange={onToggleTheme}
                label={isDark ? <WeatherMoon24Regular /> : <WeatherSunny24Regular />}
              />
            </Tooltip>
          </div>

          <Tooltip content="Settings" relationship="label">
            <Button
              appearance="subtle"
              icon={<Settings24Regular />}
              onClick={() => setSettingsOpen(true)}
              aria-label="Settings"
            />
          </Tooltip>
        </div>
      </header>

      <main className={styles.content}>{children}</main>

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
