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
  title: string;
  scenario: string;
  template: string;
  requirements: string[];
  technologies: string[];
  files: string[]; // filenames only (for display)
  saved_at: string;
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
