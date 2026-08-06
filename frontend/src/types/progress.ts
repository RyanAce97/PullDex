export interface ProgressRead {
  total_species: number;
  owned_species: number;
  missing_species: number;
  completion_percentage: number;
}

export interface MissingSpeciesRead {
  id: number;
  national_dex_number: number;
  name: string;
  generation: number | null;
}
