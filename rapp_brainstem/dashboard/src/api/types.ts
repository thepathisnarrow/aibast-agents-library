// Types matching the backend /api/dashboard/* endpoints

export interface AuthAccount {
  key: string;
  username: string;
  domain: string;
  displayName: string;
  adminAccess: boolean;
  isPrimary: boolean;
}

export interface AuthConfig {
  accounts: AuthAccount[];
}

export interface AgentInfo {
  name: string;
  description: string;
  status: 'ready' | 'busy' | 'error';
}

export interface ProjectInfo {
  id: number;
  title: string;
  description: string;
  status: 'queued' | 'in-progress' | 'completed';
  created_at: string;
  labels: string[];
  url: string;
}

export interface AzureResourceGroup {
  name: string;
  location: string;
  resources: AzureResource[];
}

export interface AzureResource {
  name: string;
  type: string;
  location: string;
}

export interface AzureCost {
  actual: number;
  forecast: number;
  currency: string;
}

export interface FabricCapacity {
  id: string;
  resourceId: string;
  name: string;
  state: 'Active' | 'Paused' | 'Deleting';
  sku: string;
  region: string;
}

export interface FabricWorkspace {
  id: string;
  name: string;
  capacityId: string;
  type: string;
  items?: FabricItem[];
}

export interface FabricItem {
  id: string;
  displayName: string;
  type: string;
}

export interface PurviewAsset {
  count: number;
  byType: Record<string, number>;
}

export interface PurviewPolicy {
  count: number;
}

export interface DemoRequest {
  id: string;
  title: string;
  customer_name: string;
  customer_website_url?: string;
  industry_primary?: string;
  industry_secondary?: string;
  azure_region?: string;
  existing_fabric_workspace_id?: string;
  scenario: string;
  template: string;
  requirements: string[];
  technologies: string[];
  status: 'draft' | 'queued' | 'in-progress' | 'completed';
  assigned_agents: string[];
  created_at: string;
  updated_at: string;
  url: string;
}

export interface DemoRequestDraft {
  id?: string;
  step: number;
  customer_name: string;
  customer_website_url?: string;
  industry_primary?: string;
  industry_secondary?: string;
  azure_region?: string;
  existing_fabric_workspace_id?: string;
  title: string;
  scenario: string;
  template: string;
  requirements: string[];
  technologies: string[];
  files: string[]; // filenames only (for display)
  saved_at: string;
}

// ── Demo run / live transcript ────────────────────────────────────────────

export type RunStatus =
  | 'queued'
  | 'running'
  | 'awaiting_user'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface PendingQuestion {
  question_id: string;
  question: string;
  context?: string;
  asked_at?: string;
}

export interface RunState {
  run_id: string;
  demo_id: string;
  demo_title: string;
  customer_name: string;
  scenario: string;
  template: string;
  requirements: string[];
  technologies: string[];
  status: RunStatus;
  pending_question: PendingQuestion | null;
  started_at: string | null;
  updated_at: string;
  completed_at: string | null;
  summary: string | null;
  error: string | null;
  event_count: number;
}

export type RunEventType =
  | 'run_queued'
  | 'run_started'
  | 'round_started'
  | 'llm_message'
  | 'tool_call'
  | 'tool_result'
  | 'question'
  | 'answer'
  | 'run_completed'
  | 'run_failed'
  | 'run_cancelled';

export interface RunEvent {
  seq: number;
  ts: string;
  type: RunEventType;
  data: Record<string, unknown>;
}

export interface RunEventsResponse {
  run_id: string;
  events: RunEvent[];
  next_since: number;
  status: RunStatus | null;
  pending_question: PendingQuestion | null;
}

export interface DashboardData {
  agents: {
    loaded: AgentInfo[];
    projects: ProjectInfo[];
  };
  azure: {
    resourceGroups: AzureResourceGroup[];
    totalResources: number;
    cost: AzureCost;
  };
  fabric: {
    capacities: FabricCapacity[];
    workspaces: FabricWorkspace[];
  };
  purview: {
    assets: PurviewAsset;
    policies: PurviewPolicy;
  };
  demos: DemoRequest[];
  timestamp: string;
}
