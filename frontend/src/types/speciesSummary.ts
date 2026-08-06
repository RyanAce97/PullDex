export interface SpeciesSummaryRead {
  species_id: number;
  national_dex_number: number;
  name: string;
  generation: number | null;
  owned: boolean;
}
