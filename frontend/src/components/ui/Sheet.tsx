import { useEffect } from "react";
import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { springGentle } from "@/lib/motion";

interface SheetProps {
  /** Open state */
  open: boolean;
  /** Called when user dismisses (backdrop click, drag-down, ESC) */
  onClose: () => void;
  /** Sheet body */
  children: ReactNode;
  /** Optional aria-label for the dialog */
  ariaLabel?: string;
}

/**
 * iOS-style bottom sheet. Renders a backdrop + grab-handle + content panel
 * that slides up from the bottom. Supports drag-to-dismiss with elastic feel.
 *
 * Used by ItemDetailsSheet and any other modal-style overlay in the app.
 */
export function Sheet({ open, onClose, children, ariaLabel }: SheetProps) {
  // ESC key dismisses
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Lock body scroll while open
  useEffect(() => {
    if (!open) return;
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = original;
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
          />

          {/* Sheet panel */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={ariaLabel}
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={springGentle}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={0.2}
            onDragEnd={(_, info) => {
              if (info.offset.y > 120 || info.velocity.y > 500) {
                onClose();
              }
            }}
            className="fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[90dvh] max-w-phone flex-col rounded-t-ios-sheet bg-surface shadow-ios-sheet pb-safe"
            dir="rtl"
          >
            {/* Grab handle — stays pinned at top while body scrolls */}
            <div className="flex flex-shrink-0 justify-center pb-1 pt-2">
              <div className="h-1 w-9 rounded-full bg-fill/40" />
            </div>
            <div className="flex-1 overflow-y-auto overscroll-contain">
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
