import { useEffect, useRef, useState } from "react";
import type { PokemonSpeciesRead } from "../types";

export interface SearchResult {
  species: PokemonSpeciesRead;
  page: number;
}

interface BinderSearchProps {
  speciesList: PokemonSpeciesRead[];
  pageSize: number;
  onSelect: (result: SearchResult) => void;
  inputRef?: React.RefObject<HTMLInputElement>;
}

/**
 * Pokémon search input with autocomplete dropdown.
 *
 * Searches by name (case-insensitive substring) and by dex number.
 * Results show "#025 Pikachu — Page 2" format.
 * Selecting a result triggers navigation to the relevant binder page.
 */
export function BinderSearch({ speciesList, pageSize, onSelect, inputRef }: BinderSearchProps) {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const results = getSearchResults(query, speciesList, pageSize);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Reset active index when results change
  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  // Scroll active item into view
  useEffect(() => {
    if (listRef.current && isOpen) {
      const activeItem = listRef.current.children[activeIndex] as HTMLElement | undefined;
      activeItem?.scrollIntoView({ block: "nearest" });
    }
  }, [activeIndex, isOpen]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!isOpen || results.length === 0) {
      if (e.key === "Escape") {
        setQuery("");
        setIsOpen(false);
        (e.target as HTMLInputElement).blur();
      }
      return;
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, results.length - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        break;
      case "Enter":
        e.preventDefault();
        if (results[activeIndex]) {
          selectResult(results[activeIndex]);
        }
        break;
      case "Escape":
        e.preventDefault();
        setQuery("");
        setIsOpen(false);
        (e.target as HTMLInputElement).blur();
        break;
    }
  }

  function selectResult(result: SearchResult) {
    setQuery("");
    setIsOpen(false);
    onSelect(result);
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <svg
          className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          ref={inputRef as React.RefObject<HTMLInputElement>}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(e.target.value.length > 0);
          }}
          onFocus={() => {
            if (query.length > 0) setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search Pokémon or Dex number..."
          className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          aria-label="Search Pokémon by name or National Dex number"
          aria-expanded={isOpen}
          aria-controls="binder-search-results"
          aria-activedescendant={isOpen && results.length > 0 ? `binder-search-result-${activeIndex}` : undefined}
          role="combobox"
          autoComplete="off"
        />
      </div>

      {isOpen && (
        <ul
          ref={listRef}
          id="binder-search-results"
          role="listbox"
          className="absolute z-50 top-full left-0 right-0 mt-1 max-h-64 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg"
        >
          {results.length === 0 ? (
            <li className="px-3 py-2.5 text-sm text-gray-500 text-center">
              No Pokémon found
            </li>
          ) : (
            results.map((result, index) => (
              <li
                key={result.species.id}
                id={`binder-search-result-${index}`}
                role="option"
                aria-selected={index === activeIndex}
                onClick={() => selectResult(result)}
                onMouseEnter={() => setActiveIndex(index)}
                className={`px-3 py-2 text-sm cursor-pointer flex items-center justify-between ${
                  index === activeIndex
                    ? "bg-indigo-50 text-indigo-900"
                    : "text-gray-700 hover:bg-gray-50"
                }`}
              >
                <span>
                  <span className="font-mono text-gray-400 mr-1.5">
                    #{String(result.species.national_dex_number).padStart(3, "0")}
                  </span>
                  <span className="capitalize font-medium">{result.species.name}</span>
                </span>
                <span className="text-xs text-gray-400 ml-2 whitespace-nowrap">
                  Page {result.page}
                </span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}

/**
 * Filter species by query and calculate target pages.
 * Searches by name substring (case-insensitive) and exact/prefix dex number.
 */
function getSearchResults(
  query: string,
  speciesList: PokemonSpeciesRead[],
  pageSize: number,
): SearchResult[] {
  const trimmed = query.trim();
  if (trimmed.length === 0) return [];

  const lower = trimmed.toLowerCase();
  const asNumber = parseInt(trimmed, 10);
  const isNumericSearch = !isNaN(asNumber) && /^\d+$/.test(trimmed);

  let matches: PokemonSpeciesRead[];

  if (isNumericSearch) {
    // Search by dex number: exact match first, then prefix
    matches = speciesList.filter((s) => {
      const dexStr = String(s.national_dex_number);
      return dexStr === trimmed || dexStr.startsWith(trimmed);
    });
  } else {
    // Search by name substring (case-insensitive)
    matches = speciesList.filter((s) => s.name.toLowerCase().includes(lower));
  }

  // Limit results to avoid an overwhelming dropdown
  const limited = matches.slice(0, 20);

  return limited.map((species) => ({
    species,
    page: Math.ceil(species.national_dex_number / pageSize),
  }));
}
