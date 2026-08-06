export interface SetSummaryRead {
  set_id: number;
  api_set_id: string | null;
  name: string;
  series: string;
  release_date: string | null;
  total_species_in_set: number;
  owned_species_in_set: number;
  missing_species_in_set: number;
}
