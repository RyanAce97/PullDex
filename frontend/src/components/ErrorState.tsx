interface ErrorStateProps {
  message?: string;
}

export function ErrorState({
  message = "Something went wrong. Is the backend running on :8000?",
}: ErrorStateProps) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <p className="text-red-700">{message}</p>
    </div>
  );
}
