interface ProgressBarProps {
  /** Value between 0 and 100. */
  percentage: number;
  /** Optional label rendered above the bar. */
  label?: string;
}

export function ProgressBar({ percentage, label }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, percentage));

  return (
    <div>
      {label && (
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium text-gray-700">{label}</span>
          <span className="text-sm font-medium text-gray-700">
            {clamped}%
          </span>
        </div>
      )}
      <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
        <div
          className="bg-indigo-600 h-3 rounded-full transition-all duration-500"
          style={{ width: `${clamped}%` }}
          role="progressbar"
          aria-valuenow={clamped}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}
