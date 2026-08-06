import { useQuery } from "@tanstack/react-query";
import { getProgress } from "../api/progress";
import { queryKeys } from "../lib/queryKeys";

export function useProgress() {
  return useQuery({
    queryKey: queryKeys.progress,
    queryFn: getProgress,
  });
}
