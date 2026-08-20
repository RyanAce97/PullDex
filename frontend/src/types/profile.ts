export interface ProfileRead {
  id: number;
  name: string;
  is_active: boolean;
  created_at: string;
  binder_rows: number;
  binder_columns: number;
  binder_sort: string;
}

export interface ProfileCreate {
  name: string;
}

export interface ProfileRename {
  name: string;
}

export interface ProfileSettingsUpdate {
  binder_rows?: number;
  binder_columns?: number;
  binder_sort?: string;
}
