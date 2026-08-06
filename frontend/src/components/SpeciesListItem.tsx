import type { PokemonSpeciesRead } from "../types";

interface SpeciesListItemProps {
  species: PokemonSpeciesRead;
  owned: boolean;
}

export function SpeciesListItem({ species, owned }: SpeciesListItemProps) {
  return (
    <div
      className={`flex items-center gap-3 rounded-lg border p-3 ${
        owned
          ? "bg-green-50 border-green-200"
          : "bg-white border-gray-200"
      }`}
    >
      <span
        className={`inline-flex items-center justify-center w-10 h-10 rounded-full text-sm font-mono font-bold ${
          owned
            ? "bg-green-100 text-green-700"
            : "bg-gray-100 text-gray-500"
        }`}
      >
        #{species.national_dex_number}
      </span>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-900 capitalize truncate">
          {species.name}
        </p>
        {species.generation !== null && (
          <p className="text-xs text-gray-500">Gen {species.generation}</p>
        )}
      </div>
      <span
        className={`text-xs font-semibold px-2 py-1 rounded-full ${
          owned
            ? "bg-green-100 text-green-700"
            : "bg-gray-100 text-gray-500"
        }`}
      >
        {owned ? "Owned" : "Missing"}
      </span>
    </div>
  );
}
