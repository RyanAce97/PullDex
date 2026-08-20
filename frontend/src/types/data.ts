export interface ExportResponse {
  format_version: number;
  exported_at: string;
  app_version: string;
  profile: {
    name: string;
    binder_rows: number;
    binder_columns: number;
    binder_sort: string;
  };
  collection: Array<{
    type: "species" | "card";
    national_dex_number?: number;
    species_name?: string;
    api_card_id?: string;
    quantity?: number;
  }>;
}

export interface ImportRequest {
  data: ExportResponse;
  mode: "new_profile" | "replace" | "merge";
}

export interface ImportResponse {
  imported_species: number;
  imported_cards: number;
  skipped_species: number;
  skipped_cards: number;
  warnings: string[];
  total_imported: number;
  total_skipped: number;
  has_backup: boolean;
}

export interface BackupResponse {
  success: boolean;
  backup_path: string | null;
  error: string | null;
}

export interface RestoreRequest {
  backup_path: string;
}

export interface RestoreResponse {
  success: boolean;
  errors: string[];
  pre_restore_backup: string | null;
  message: string | null;
}
