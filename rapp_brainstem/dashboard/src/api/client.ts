import type { DashboardData, DemoRequest, AuthConfig, AuthAccount } from './types';

const BASE = '/api/dashboard';

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${resp.statusText}`);
  }
  return resp.json() as Promise<T>;
}

export interface CapacityActionResult {
  status: 'succeeded' | 'warning' | 'error';
  action: string;
  message?: string;
}

export async function capacityAction(resourceId: string, action: 'resume' | 'suspend'): Promise<CapacityActionResult> {
  const resp = await fetch(`${BASE}/fabric/capacity/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resourceId }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    return { status: 'error', action, message: err.error || `Failed to ${action} capacity` };
  }
  return resp.json() as Promise<CapacityActionResult>;
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

export async function fetchDemoRequests(): Promise<DemoRequest[]> {
  return fetchJson<DemoRequest[]>(`${BASE}/demos`);
}

export async function submitDemoRequest(data: {
  title: string;
  customer_name: string;
  scenario: string;
  template: string;
  requirements: string[];
  technologies: string[];
  files?: File[];
}): Promise<{ id: string; url: string }> {
  const formData = new FormData();
  formData.append('title', data.title);
  formData.append('customer_name', data.customer_name);
  formData.append('scenario', data.scenario);
  formData.append('template', data.template);
  formData.append('requirements', JSON.stringify(data.requirements));
  formData.append('technologies', JSON.stringify(data.technologies));
  if (data.files) {
    for (const file of data.files) {
      formData.append('files', file);
    }
  }
  const resp = await fetch(`${BASE}/demos`, {
    method: 'POST',
    body: formData,
  });
  if (!resp.ok) {
    throw new Error(`Failed to submit demo request: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchAuthConfig(): Promise<AuthConfig> {
  return fetchJson<AuthConfig>(`${BASE}/auth`);
}

export async function saveAuthConfig(accounts: AuthAccount[]): Promise<void> {
  const resp = await fetch(`${BASE}/auth`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ accounts }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to save auth config: ${resp.statusText}`);
  }
}
