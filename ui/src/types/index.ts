export interface InputReference {
  node_id: string;
  output_id: string;
}

export interface NodeInput {
  name: string;
  file_type: string;
  values?: any[];
  input_references: InputReference[];
  primitive_override?: any;
  is_array?: boolean;
  min_count?: number;
  [key: string]: any;
}

export interface NodeOutput {
  name: string;
  file_type: string;
  values: any[];
  thumbnail?: string;
  is_array?: boolean;
  min_count?: number;
  [key: string]: any;
}

export interface NodeParameter {
  name: string;
  parameter_type: string;
  value: any;
  widget?: string | null;
  reference?: string | null;
  [key: string]: any;
}

export interface CachedNode {
  node_running_status?: string;
  outputs?: NodeOutput[];
  logs?: any[];
  [key: string]: any;
}

export interface NodeData {
  _id: string;
  title: string;
  description?: string;
  kind: string;
  inputs: NodeInput[];
  outputs: NodeOutput[];
  parameters: NodeParameter[];
  logs?: any[];
  node_status?: string;
  node_running_status?: string;
  parent_node_id?: string | null;
  successor_node_id?: string | null;
  insertion_date?: string;
  update_date?: string;
  x?: number;
  y?: number;
  _cached_node?: CachedNode;
  _user?: any[];
  _readonly?: boolean;
  [key: string]: any;
}

export interface ResourceDescriptor {
  name: string;
  alias: string;
  icon: string;
  color: string;
  display_raw?: boolean;
  [key: string]: any;
}

export interface ExecutorInfo {
  title: string;
  icon: string;
  color: string;
  is_workflow?: boolean;
  operations?: any[];
  [key: string]: any;
}

export interface PluginsDict {
  resources_dict: Record<string, ResourceDescriptor>;
  executors_info: Record<string, ExecutorInfo>;
  operations_dict?: Record<string, any>;
  hubs_dict?: Record<string, any>;
  [key: string]: any;
}

export interface UserSettings {
  display_name?: string;
  [key: string]: any;
}

export interface User {
  username: string;
  settings?: UserSettings;
  policies?: string[];
  _is_admin?: boolean;
  _readonly?: boolean;
  [key: string]: any;
}

export interface PreviewData {
  title: string;
  file_type: string;
  resource_id?: string;
  values?: any[];
  download_name: string;
  display_raw?: boolean;
  is_array?: boolean;
}
