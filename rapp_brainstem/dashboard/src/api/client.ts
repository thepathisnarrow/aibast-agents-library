import type { DashboardData } from './types';

const BASE = '/api/dashboard';

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${resp.statusText}`);
  }
  return resp.json() as Promise<T>;
}

export async function fetchDashboardData(): Promise<DashboardData> {
  return fetchJson<DashboardData>(`${BASE}/overview`);
}

export async function submitProject(data: {
  title: string;
  description: string;
  files?: File[];
}): Promise<{ id: number; url: string }> {
  const formData = new FormData();
  formData.append('title', data.title);
  formData.append('description', data.description);
  if (data.files) {
    for (const file of data.files) {
      formData.append('files', file);
    }
  }
  const resp = await fetch(`${BASE}/projects`, {
    method: 'POST',
    body: formData,
  });
  if (!resp.ok) {
    throw new Error(`Failed to submit project: ${resp.statusText}`);
  }
  return resp.json();
}
