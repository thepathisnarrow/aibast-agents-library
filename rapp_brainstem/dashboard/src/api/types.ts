// Types matching the backend /api/dashboard/* endpoints

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
  timestamp: string;
}
