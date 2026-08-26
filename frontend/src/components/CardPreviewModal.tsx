import { useEffect } from "react";

interface CardPreviewModalProps {
  /** URL to the card image */
  imageUrl: string;
  /** Alt text for the image */
  alt?: string;
  /** Optional card details to display below the image */
  details?: {
    name?: string | null;
    setName?: string | null;
    setCode?: string | null;
    rarity?: string | null;
    cardNumber?: string | null;
    dexNumber?: number | null;
  };
  /** Called when the modal should close */
  onClose: () => void;
}

/**
 * Reusable modal for previewing card images at a larger size.
 *
 * Features:
 * - Displays the card image large while maintaining aspect ratio
 * - Closes on: Escape key, click outside, close button
 * - Shows optional card details below the image
 * - Does NOT perform any mutations (read-only preview)
 */
export function CardPreviewModal({ imageUrl, alt, details, onClose }: CardPreviewModalProps) {
  // Escape key closes modal
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Card preview"
    >
      <div className="relative max-w-lg w-full mx-4 flex flex-col items-center">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute -top-3 -right-3 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-white shadow-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
          aria-label="Close preview"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Card image */}
        <img
          src={imageUrl}
          alt={alt ?? "Card preview"}
          className="max-h-[75vh] w-auto object-contain rounded-xl shadow-2xl"
        />

        {/* Optional details */}
        {details && (
          <div className="mt-3 bg-white/90 backdrop-blur-sm rounded-lg px-4 py-2 shadow-md flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            {details.name && (
              <span className="font-semibold text-gray-900 capitalize">{details.name}</span>
            )}
            {details.dexNumber && (
              <span className="text-gray-400 font-mono text-xs">
                #{String(details.dexNumber).padStart(3, "0")}
              </span>
            )}
            {details.setName && (
              <span className="text-gray-600">{details.setName}</span>
            )}
            {details.rarity && (
              <span className="text-gray-500 text-xs">{details.rarity}</span>
            )}
            {details.cardNumber && (
              <span className="text-gray-400 text-xs">#{details.cardNumber}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
