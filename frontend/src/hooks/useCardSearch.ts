import { useQuery } from "@tanstack/react-query";
import { searchCardsFull } from "../api/cards";

export function useCardSearch(query: string) {
  return useQuery({
    queryKey: ["cards", "search", query],
    queryFn: () => searchCardsFull(query, 50),
    enabled: query.length >= 2,
  });
}
