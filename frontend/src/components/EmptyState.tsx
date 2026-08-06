interface EmptyStateProps {
  message: string;
  icon?: string;
}

export function EmptyState({ message, icon = "📭" }: EmptyStateProps) {
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
      <p className="text-2xl mb-2" aria-hidden="true">
        {icon}
      </p>
      <p className="text-gray-600 font-medium">{message}</p>
    </div>
  );
}
