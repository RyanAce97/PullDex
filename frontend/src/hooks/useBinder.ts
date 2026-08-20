import { useQuery } from "@tanstack/react-query";
import { getBinderPage } from "../api/binder";
import type { BinderParams } from "../api/binder";
import { queryKeys } from "../lib/queryKeys";

export function useBinderPage(params: BinderParams) {
  return useQuery({
    queryKey: queryKeys.binderCards(params as Record<string, unknown>),
    queryFn: () => getBinderPage(params),
  });
}
