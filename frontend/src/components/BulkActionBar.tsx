import { Trash2, CheckCircle, RotateCcw, X, GitMerge } from "lucide-react";
import { motion } from "motion/react";
import { springGentle, springSnappy, tapScale } from "@/lib/motion";

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
      <motion.div
        layout
        transition={springGentle}
        className="flex w-full max-w-[430px] items-center gap-2 rounded-ios-lg border border-separator/40 bg-surface px-4 py-3 shadow-ios-lg"
        dir="rtl"
      >
        <span className="text-footnote font-bold text-label">
          {selectedCount} נבחרו
        </span>

        <div className="flex-1" />

        <motion.button
          type="button"
          onClick={onComplete}
          whileTap={tapScale}
          transition={springSnappy}
          className="flex items-center gap-1 rounded-ios-sm bg-brand/15 px-3 py-1.5 text-footnote font-medium text-brand transition-colors hover:bg-brand/20"
        >
          <CheckCircle className="h-3.5 w-3.5" />
          השלם
        </motion.button>

        <motion.button
          type="button"
          onClick={onActivate}
          whileTap={tapScale}
          transition={springSnappy}
          className="flex items-center gap-1 rounded-ios-sm bg-accent-blue/15 px-3 py-1.5 text-footnote font-medium text-accent-blue transition-colors hover:bg-accent-blue/20"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          הפעל
        </motion.button>

        {canMerge && (
          <motion.button
            type="button"
            onClick={onMerge}
            whileTap={tapScale}
            transition={springSnappy}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="flex items-center gap-1 rounded-ios-sm bg-accent-purple/15 px-3 py-1.5 text-footnote font-medium text-accent-purple transition-colors hover:bg-accent-purple/20"
            title="אחד את הפריטים הנבחרים לפריט אחד"
          >
            <GitMerge className="h-3.5 w-3.5" />
            אחד
          </motion.button>
        )}

        <motion.button
          type="button"
          onClick={onDelete}
          whileTap={tapScale}
          transition={springSnappy}
          className="flex items-center gap-1 rounded-ios-sm bg-danger/15 px-3 py-1.5 text-footnote font-medium text-danger transition-colors hover:bg-danger/20"
        >
          <Trash2 className="h-3.5 w-3.5" />
          מחק
        </motion.button>

        <motion.button
          type="button"
          onClick={onCancel}
          whileTap={tapScale}
          transition={springSnappy}
          className="rounded-ios-sm p-1.5 text-label-tertiary transition-colors hover:bg-fill/15 hover:text-label-secondary"
          aria-label="ביטול"
        >
          <X className="h-4 w-4" />
        </motion.button>
      </motion.div>
    </div>
  );
}
