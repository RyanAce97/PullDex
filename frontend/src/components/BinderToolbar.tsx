import { useRef, useState } from "react";
import { BinderSearch } from "./BinderSearch";
import type { SearchResult } from "./BinderSearch";
import type { PokemonSpeciesRead } from "../types";

interface BinderToolbarProps {
  page: number;
  totalPages: number;
  pageSize: number;
  speciesList: PokemonSpeciesRead[];
  onPageChange: (page: number) => void;
  onSearchSelect: (result: SearchResult) => void;
  searchInputRef: React.RefObject<HTMLInputElement>;
  /** Dex range for current page */
  startDex: number;
  endDex: number;
}

/**
 * Combined toolbar for the Binder page.
 * Contains: search input, dex range display, and pagination controls.
 */
export function BinderToolbar({
  page,
  totalPages,
  pageSize,
  speciesList,
  onPageChange,
  onSearchSelect,
  searchInputRef,
  startDex,
  endDex,
}: BinderToolbarProps) {
  const [pageInput, setPageInput] = useState(String(page));
  const pageInputRef = useRef<HTMLInputElement>(null);

  // Keep pageInput in sync with external page changes
  if (pageInput !== String(page) && document.activeElement !== pageInputRef.current) {
    setPageInput(String(page));
  }

  function handlePageSubmit() {
    const parsed = parseInt(pageInput, 10);
    if (isNaN(parsed)) {
      setPageInput(String(page));
      return;
    }
    const clamped = Math.max(1, Math.min(totalPages, parsed));
    setPageInput(String(clamped));
    onPageChange(clamped);
  }

  function handlePageInputKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      handlePageSubmit();
      pageInputRef.current?.blur();
    }
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Search */}
      <div className="w-72 flex-shrink-0">
        <BinderSearch
          speciesList={speciesList}
          pageSize={pageSize}
          onSelect={onSearchSelect}
          inputRef={searchInputRef}
        />
      </div>

      {/* Dex range */}
      <span className="text-xs text-gray-400 font-mono hidden sm:inline">
        #{String(startDex).padStart(3, "0")}–#{String(endDex).padStart(3, "0")}
      </span>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Pagination controls */}
      <div className="flex items-center gap-1.5">
        {/* First */}
        <button
          onClick={() => onPageChange(1)}
          disabled={page <= 1}
          className="p-1.5 text-sm rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="First page"
          title="First page"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
            <path d="M4 2v12l-2-1V3l2-1zm2 6l6-5v10l-6-5z" />
          </svg>
        </button>

        {/* Previous */}
        <button
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="p-1.5 text-sm rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="Previous page"
          title="Previous page"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
            <path d="M10 2L4 8l6 6V2z" />
          </svg>
        </button>

        {/* Page input */}
        <span className="flex items-center gap-1 text-sm text-gray-600">
          <span className="text-gray-400">Page</span>
          <input
            ref={pageInputRef}
            type="text"
            inputMode="numeric"
            value={pageInput}
            onChange={(e) => setPageInput(e.target.value)}
            onBlur={handlePageSubmit}
            onKeyDown={handlePageInputKeyDown}
            className="w-10 text-center px-1 py-0.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            aria-label="Page number"
          />
          <span className="text-gray-400">/ {totalPages}</span>
        </span>

        {/* Next */}
        <button
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          className="p-1.5 text-sm rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="Next page"
          title="Next page"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
            <path d="M6 2l6 6-6 6V2z" />
          </svg>
        </button>

        {/* Last */}
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={page >= totalPages}
          className="p-1.5 text-sm rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="Last page"
          title="Last page"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
            <path d="M12 2v12l2-1V3l-2-1zm-2 6L4 3v10l6-5z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
