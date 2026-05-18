import {
  FluentProvider,
  webDarkTheme,
  webLightTheme,
  tokens,
} from '@fluentui/react-components';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import { Shell } from './components/Shell';
import { OverviewPage } from './pages/OverviewPage';
import { AgentsPage } from './pages/AgentsPage';
import { AzurePage } from './pages/AzurePage';
import { FabricPage } from './pages/FabricPage';
import { PurviewPage } from './pages/PurviewPage';
import type { DashboardData } from './api/types';
import { fetchDashboardData } from './api/client';

export function App() {
  const [isDark, setIsDark] = useState(true);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshInterval, setRefreshInterval] = useState(30000);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const result = await fetchDashboardData();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    if (refreshInterval === 0) return;
    const interval = setInterval(refresh, refreshInterval);
    return () => clearInterval(interval);
  }, [refresh, refreshInterval]);

  return (
    <FluentProvider
      theme={isDark ? webDarkTheme : webLightTheme}
      style={{
        minHeight: '100vh',
        backgroundColor: tokens.colorNeutralBackground1,
      }}
    >
      <BrowserRouter basename="/dashboard">
        <Shell isDark={isDark} onToggleTheme={() => setIsDark(!isDark)} refreshInterval={refreshInterval} onRefreshIntervalChange={setRefreshInterval}>
          <Routes>
            <Route path="/" element={<OverviewPage data={data} loading={loading} error={error} onRefresh={refresh} />} />
            <Route path="/agents" element={<AgentsPage data={data} loading={loading} error={error} onRefresh={refresh} />} />
            <Route path="/azure" element={<AzurePage data={data} loading={loading} error={error} onRefresh={refresh} />} />
            <Route path="/fabric" element={<FabricPage data={data} loading={loading} error={error} onRefresh={refresh} />} />
            <Route path="/purview" element={<PurviewPage data={data} loading={loading} error={error} onRefresh={refresh} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Shell>
      </BrowserRouter>
    </FluentProvider>
  );
}
