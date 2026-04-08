import { Trash2, CheckCircle, RotateCcw, X, GitMerge } from "lucide-react";

interface BulkActionBarProps {
  selectedCount: number;
  onComplete: () => void;
  onActivate: () => void;
  onDelete: () => void;
  onCancel: () => void;
  onMerge?: () => void;
}

export function BulkActionBar({
  selectedCount,
  onComplete,
  onActivate,
  onDelete,
  onCancel,
  onMerge,
}: BulkActionBarProps) {
  if (selectedCount === 0) return null;

  // The merge action requires at least two items (target + at least one source).
  const canMerge = onMerge !== undefined && selectedCount >= 2;

  return (
    <div className="fixed inset-x-0 bottom-16 z-40 flex items-center justify-center px-4">
      <div
        className="flex w-full max-w-[430px] items-center gap-2 rounded-2xl bg-white px-4 py-3 shadow-lg border border-gray-200"
        dir="rtl"
      >
        <span className="text-[13px] font-bold text-gray-700">
          {selectedCount} נבחרו
        </span>

        <div className="flex-1" />

        <button
          type="button"
          onClick={onComplete}
          className="flex items-center gap-1 rounded-lg bg-green-50 px-3 py-1.5 text-[13px] font-medium text-green-700 hover:bg-green-100"
        >
          <CheckCircle className="h-3.5 w-3.5" />
          השלם
        </button>

        <button
          type="button"
          onClick={onActivate}
          className="flex items-center gap-1 rounded-lg bg-blue-50 px-3 py-1.5 text-[13px] font-medium text-blue-700 hover:bg-blue-100"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          הפעל
        </button>

        {canMerge && (
          <button
            type="button"
            onClick={onMerge}
            className="flex items-center gap-1 rounded-lg bg-purple-50 px-3 py-1.5 text-[13px] font-medium text-purple-700 hover:bg-purple-100"
            title="אחד את הפריטים הנבחרים לפריט אחד"
          >
            <GitMerge className="h-3.5 w-3.5" />
            אחד
          </button>
        )}

        <button
          type="button"
          onClick={onDelete}
          className="flex items-center gap-1 rounded-lg bg-red-50 px-3 py-1.5 text-[13px] font-medium text-red-600 hover:bg-red-100"
        >
          <Trash2 className="h-3.5 w-3.5" />
          מחק
        </button>

        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100"
          aria-label="ביטול"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
