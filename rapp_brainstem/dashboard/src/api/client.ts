import type {
  DashboardData,
  DemoRequest,
  AuthConfig,
  AuthAccount,
  RunState,
  RunEventsResponse,
} from './types';

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
  customer_website_url?: string;
  industry_primary: string;
  industry_secondary?: string;
  azure_region?: string;
  existing_fabric_workspace_id?: string;
  scenario: string;
  template: string;
  requirements: string[];
  technologies: string[];
  files?: File[];
}): Promise<{ id: string; url: string }> {
  const formData = new FormData();
  formData.append('title', data.title);
  formData.append('customer_name', data.customer_name);
  formData.append('customer_website_url', data.customer_website_url || '');
  formData.append('industry_primary', data.industry_primary || '');
  formData.append('industry_secondary', data.industry_secondary || '');
  formData.append('azure_region', data.azure_region || 'westus3');
  formData.append('existing_fabric_workspace_id', data.existing_fabric_workspace_id || '');
  formData.append('scenario', data.scenario);
  formData.append('template', data.template);
  formData.append('requirements', JSON.stringify(data.requirements));
  formData.append('technologies', JSON.stringify(data.technologies));
  if (data.files) {
    for (const file of data.files) {
      formData.append('files', file);
    }
  }
  let resp: Response;
  try {
    resp = await fetch(`${BASE}/demos`, {
      method: 'POST',
      body: formData,
    });
  } catch (err) {
    // fetch() throws TypeError on network-level failures (server down, CORS, DNS, etc.)
    // The default message is just "Failed to fetch" which gives the user nothing to act on.
    const detail = err instanceof Error ? err.message : String(err);
    throw new Error(
      `Cannot reach the Brainstem server. Is it running on http://localhost:7071? (${detail})`
    );
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      if (body?.error) detail = body.error + (body.detail ? `: ${body.detail}` : '');
    } catch {
      // ignore JSON parse failure
    }
    throw new Error(`Failed to submit demo request (${resp.status}): ${detail}`);
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

// ── GitHub device-code login (uses brainstem's /login + /login/poll) ─────────

export interface GitHubLoginStart {
  user_code: string;
  verification_uri: string;
}

export interface GitHubLoginPoll {
  status?: 'ok' | 'pending';
  message?: string;
  error?: string;
}

export interface GitHubAuthStatus {
  authenticated: boolean;
  copilot: boolean;
  pending: boolean;
}

export async function startGitHubLogin(): Promise<GitHubLoginStart> {
  const resp = await fetch('/login', { method: 'POST' });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body?.error || `Failed to start login (${resp.status})`);
  }
  return resp.json();
}

export async function pollGitHubLogin(): Promise<GitHubLoginPoll> {
  const resp = await fetch('/login/poll', { method: 'POST' });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(body?.error || `Login poll failed (${resp.status})`);
  }
  return body;
}

export async function fetchGitHubAuthStatus(): Promise<GitHubAuthStatus> {
  const [healthResp, pendingResp] = await Promise.all([
    fetch('/health'),
    fetch('/login/status'),
  ]);
  const health = await healthResp.json().catch(() => ({}));
  const pending = await pendingResp.json().catch(() => ({}));
  return {
    authenticated: health?.status === 'ok',
    copilot: health?.copilot === '\u2713',
    pending: !!pending?.pending,
  };
}

// ── Demo runs (background worker) ─────────────────────────────────────────

export async function startDemoRun(demoId: string): Promise<RunState> {
  const resp = await fetch(`${BASE}/demos/${demoId}/run`, { method: 'POST' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error || `Failed to start run (${resp.status})`);
  }
  return resp.json();
}

export async function fetchRunsForDemo(demoId: string): Promise<RunState[]> {
  const resp = await fetch(`${BASE}/demos/${demoId}/runs`);
  if (!resp.ok) return [];
  const body = await resp.json();
  return (body?.runs as RunState[]) || [];
}

export async function fetchRunState(runId: string): Promise<RunState> {
  return fetchJson<RunState>(`${BASE}/runs/${runId}`);
}

export async function fetchRunEvents(runId: string, since: number): Promise<RunEventsResponse> {
  return fetchJson<RunEventsResponse>(`${BASE}/runs/${runId}/events?since=${since}`);
}

export async function answerRunQuestion(
  runId: string,
  questionId: string,
  answer: string,
): Promise<void> {
  const resp = await fetch(`${BASE}/runs/${runId}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question_id: questionId, answer }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error || `Failed to submit answer (${resp.status})`);
  }
}

export async function cancelRun(runId: string): Promise<void> {
  await fetch(`${BASE}/runs/${runId}/cancel`, { method: 'POST' });
}

export async function fetchAwaitingUserRuns(): Promise<RunState[]> {
  try {
    const body = await fetchJson<{ runs: RunState[] }>(`${BASE}/runs/awaiting_user`);
    return body.runs || [];
  } catch {
    return [];
  }
}
