# PullDex Frontend — Developer Guide

## Folder Structure

```
frontend/
├── index.html                    # Vite entry HTML
├── package.json                  # Dependencies and scripts
├── tsconfig.json                 # TypeScript config (strict mode)
├── vite.config.ts                # Vite + React plugin + path aliases
├── tailwind.config.ts            # Tailwind content paths
├── postcss.config.js             # PostCSS with Tailwind + Autoprefixer
├── .env                          # Environment variables (VITE_API_URL)
└── src/
    ├── main.tsx                  # React entry: QueryClient, BrowserRouter, App
    ├── App.tsx                   # Route definitions
    ├── index.css                 # Tailwind directives + base styles
    ├── vite-env.d.ts             # Vite/env type declarations
    ├── api/                      # HTTP functions (no React)
    │   ├── client.ts             # Base fetch wrapper
    │   ├── cards.ts
    │   ├── collection.ts
    │   ├── progress.ts
    │   ├── recommendations.ts
    │   └── species.ts
    ├── types/                    # TypeScript interfaces (mirror backend schemas)
    │   ├── index.ts              # Barrel re-export
    │   ├── card.ts
    │   ├── collection.ts
    │   ├── progress.ts
    │   ├── recommendation.ts
    │   ├── set.ts
    │   └── species.ts
    ├── lib/                      # Shared utilities and constants
    │   ├── constants.ts          # NATIONAL_DEX_COUNT, etc.
    │   └── queryKeys.ts          # Centralised React Query keys
    ├── hooks/                    # React Query hooks (thin wrappers)
    │   ├── useCollection.ts
    │   ├── useMissingSpeciesQuery.ts
    │   ├── usePokedex.ts
    │   ├── useProgress.ts
    │   ├── useRecommendations.ts
    │   ├── useRecommendationSpecies.ts
    │   ├── useSpeciesDetail.ts
    │   └── useSpeciesQuery.ts
    ├── components/               # Reusable, presentation-only UI
    │   ├── EmptyState.tsx
    │   ├── ErrorBoundary.tsx
    │   ├── ErrorState.tsx
    │   ├── Layout.tsx
    │   ├── LoadingSpinner.tsx
    │   ├── ProgressBar.tsx
    │   ├── RecommendationCard.tsx
    │   ├── SpeciesListItem.tsx
    │   └── StatCard.tsx
    └── pages/                    # Route-level components
        ├── Dashboard.tsx
        ├── Pokedex.tsx
        ├── RecommendationDetail.tsx
        ├── Recommendations.tsx
        └── SpeciesDetail.tsx
```

---

## API Layer Pattern

### Structure: `src/api/`

Each file corresponds to one backend resource. Files export **plain async functions** — no React, no hooks, no state.

```typescript
// src/api/species.ts
import { apiClient } from "./client";
import { NATIONAL_DEX_COUNT } from "../lib/constants";
import type { PokemonSpeciesRead } from "../types";

export async function getAllSpecies(
  limit: number = NATIONAL_DEX_COUNT,
  offset: number = 0,
): Promise<PokemonSpeciesRead[]> {
  return apiClient.get<PokemonSpeciesRead[]>("/species", { limit, offset });
}
```

### Rules

- Every function is fully typed: parameters and return type.
- Paths start with `/` (e.g. `/recommendations`, not `recommendations`).
- Query parameters are passed as the second argument to `apiClient.get`.
- Request body is passed as the second argument to `apiClient.post`.
- Functions throw `ApiError` on non-2xx responses — callers don't need to check `.ok`.
- No business logic lives here — just HTTP transport.

### `apiClient` methods

| Method | Signature | Notes |
|--------|-----------|-------|
| `get<T>` | `(path, params?) → Promise<T>` | Appends params as URL query string |
| `post<T>` | `(path, body) → Promise<T>` | Sends JSON body, returns parsed response |
| `delete` | `(path) → Promise<void>` | Returns void on 2xx, throws on error |

### Environment

`VITE_API_URL` controls the backend base URL. Defaults to `http://localhost:8000`.

---

## React Query Conventions

### Query Keys — `src/lib/queryKeys.ts`

All keys are defined in one file. Hooks reference these constants — never inline arrays.

```typescript
export const queryKeys = {
  progress: ["progress"] as const,
  missingSpecies: ["progress", "missing"] as const,
  species: ["species"] as const,
  collection: ["collection"] as const,
  cardsByDex: (dexNumber: number) => ["cards", "by-dex", dexNumber] as const,
  recommendations: (limit: number) => ["recommendations", limit] as const,
  recommendationSpecies: (setId: number) => ["recommendations", setId, "species"] as const,
} as const;
```

**Why:** Prevents key drift between hooks. Makes invalidation predictable. Enables prefix-based invalidation (e.g. `["recommendations"]` invalidates all recommendation queries).

### Hook Pattern — `src/hooks/`

Hooks are thin wrappers around `useQuery` or `useMutation`. They encapsulate:
- The query key
- The query function (calling an API module function)
- Any `enabled` conditions

```typescript
// src/hooks/useProgress.ts
import { useQuery } from "@tanstack/react-query";
import { getProgress } from "../api/progress";
import { queryKeys } from "../lib/queryKeys";

export function useProgress() {
  return useQuery({
    queryKey: queryKeys.progress,
    queryFn: getProgress,
  });
}
```

### Composite Hooks

When a page needs multiple queries, compose reusable hooks into a single hook that returns combined `{ data, isLoading, error }`:

```typescript
// src/hooks/usePokedex.ts
export function usePokedex(): UsePokedexResult {
  const speciesQuery = useSpeciesQuery();
  const missingQuery = useMissingSpeciesQuery();
  const progressQuery = useProgress();
  // ... combine and return
}
```

### Mutations

Mutations follow this pattern:
1. Optimistic update via `onMutate`
2. Rollback via `onError`
3. Invalidate dependent queries via `onSettled`

```typescript
export function useAddToCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cardId: number) => addToCollection(cardId),
    onMutate: async (cardId) => { /* optimistic update */ },
    onError: (_err, _vars, context) => { /* rollback */ },
    onSettled: () => { /* invalidate queries */ },
  });
}
```

### Global Defaults (`main.tsx`)

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,  // 30 seconds before refetch
      retry: 1,           // One retry on failure
    },
  },
});
```

---

## Component Patterns

### Presentation Components — `src/components/`

- Receive data via typed props
- No internal data fetching
- No `useQuery`, `useMutation`, `useNavigate`, or `useParams`
- Stateless where possible (local UI state like `useState` is fine for interactive elements)
- Export named functions (no default exports)

```typescript
interface StatCardProps {
  label: string;
  value: string | number;
}

export function StatCard({ label, value }: StatCardProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-semibold text-gray-900">{value}</p>
    </div>
  );
}
```

### Interactive Components

Components that accept `onClick` should also handle keyboard accessibility:

```typescript
onClick={onClick}
role={onClick ? "button" : undefined}
tabIndex={onClick ? 0 : undefined}
onKeyDown={onClick ? (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    onClick();
  }
} : undefined}
```

### Shared UI Primitives

| Component | Props | Use for |
|-----------|-------|---------|
| `LoadingSpinner` | `message?: string` | Any loading state |
| `ErrorState` | `message?: string` | Any error state |
| `EmptyState` | `message: string, icon?: string` | Empty results |
| `ProgressBar` | `percentage: number, label?: string` | Completion bars |
| `StatCard` | `label: string, value: string \| number` | Dashboard stats |

### Error Boundary

`ErrorBoundary` wraps the `<Outlet />` in Layout. If a page throws during render, the nav stays visible and a fallback UI appears with a "Try again" button.

---

## How to Add a New Page

### 1. Create the API function (if needed)

```
src/api/newResource.ts
```

Import `apiClient`, define typed async functions.

### 2. Add TypeScript types

```
src/types/newResource.ts
```

Mirror the backend response schema exactly (snake_case field names).

Export from `src/types/index.ts`.

### 3. Add query key

```typescript
// src/lib/queryKeys.ts
export const queryKeys = {
  // ...existing
  newResource: ["new-resource"] as const,
};
```

### 4. Create the hook

```
src/hooks/useNewResource.ts
```

```typescript
import { useQuery } from "@tanstack/react-query";
import { getNewResource } from "../api/newResource";
import { queryKeys } from "../lib/queryKeys";

export function useNewResource() {
  return useQuery({
    queryKey: queryKeys.newResource,
    queryFn: getNewResource,
  });
}
```

### 5. Create the page component

```
src/pages/NewPage.tsx
```

```typescript
import { useNewResource } from "../hooks/useNewResource";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";

export function NewPage() {
  const { data, isLoading, error } = useNewResource();

  if (isLoading) return <LoadingSpinner message="Loading..." />;
  if (error) return <ErrorState />;
  if (!data) return null;

  return <div>...</div>;
}
```

### 6. Register the route

```typescript
// src/App.tsx
import { NewPage } from "./pages/NewPage";

<Route path="new-page" element={<NewPage />} />
```

### 7. Add navigation link (if top-level)

```typescript
// src/components/Layout.tsx
const navItems = [
  // ...existing
  { to: "/new-page", label: "New Page" },
];
```

---

## How to Add a New API Endpoint

When a new backend endpoint is created, follow this checklist:

### Backend returns new schema → add type

```typescript
// src/types/foo.ts
export interface FooRead {
  id: number;
  name: string;
  // match backend schema exactly
}
```

Add to `src/types/index.ts` barrel export.

### Add API function

```typescript
// src/api/foo.ts
import { apiClient } from "./client";
import type { FooRead } from "../types";

export async function getFoos(limit: number = 50): Promise<FooRead[]> {
  return apiClient.get<FooRead[]>("/foos", { limit });
}
```

### Add query key

```typescript
// src/lib/queryKeys.ts
foos: ["foos"] as const,
```

### Add hook

```typescript
// src/hooks/useFoos.ts
import { useQuery } from "@tanstack/react-query";
import { getFoos } from "../api/foo";
import { queryKeys } from "../lib/queryKeys";

export function useFoos(limit: number = 50) {
  return useQuery({
    queryKey: queryKeys.foos,
    queryFn: () => getFoos(limit),
  });
}
```

### For mutations (POST/DELETE)

```typescript
export function useCreateFoo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: FooCreate) => createFoo(body),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.foos });
    },
  });
}
```

---

## Development Commands

```bash
cd frontend
npm install       # Install dependencies
npm run dev       # Start dev server on :5173
npm run build     # Type-check + production build
npm run preview   # Preview production build locally
npx tsc --noEmit  # Type-check without building
```

## Key Decisions

- **snake_case in types:** Field names match the backend JSON exactly. No camelCase transformation layer.
- **Named exports only:** Better IDE refactoring support, explicit imports.
- **No default exports:** Prevents anonymous components in React DevTools.
- **Tailwind for styling:** No component library. Utility classes directly in JSX.
- **No global state management:** React Query handles server state. Local state via `useState` where needed.
- **No `any` types:** Strict TypeScript enforced via `tsconfig.json` with `noUnusedLocals` and `noUnusedParameters`.
