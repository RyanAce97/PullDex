export interface SetRecommendation {
  rank: number;
  set_id: number;
  api_set_id: string | null;
  set_name: string;
  series: string;
  release_date: string | null;
  missing_species_count: number;
  total_species_in_set: number;
  total_cards_in_set: number;
  coverage_percentage: number;
  missing_species_density_percentage: number;
}

export interface RecommendationResponse {
  total_species: number;
  owned_species: number;
  total_missing_species: number;
  recommendations: SetRecommendation[];
}
