import { useEffect, useState, useCallback } from "react";
import { X, AlertCircle, CheckCircle2, Info } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { springGentle } from "@/lib/motion";

interface ToastMessage {
  id: number;
  text: string;
  type: "error" | "success" | "info";
}

let nextId = 0;
let addToastExternal: ((text: string, type?: ToastMessage["type"]) => void) | null = null;

/** Show a toast from anywhere (non-React code like interceptors). */
export function showToast(text: string, type: ToastMessage["type"] = "error") {
  addToastExternal?.(text, type);
}

const ICONS: Record<ToastMessage["type"], typeof AlertCircle> = {
  error: AlertCircle,
  success: CheckCircle2,
  info: Info,
};

const COLORS: Record<ToastMessage["type"], string> = {
  error: "text-danger",
  success: "text-brand",
  info: "text-accent-blue",
};

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback(
    (text: string, type: ToastMessage["type"] = "error") => {
      const id = nextId++;
      setToasts((prev) => [...prev, { id, text, type }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4000);
    },
    [],
  );

  useEffect(() => {
    addToastExternal = addToast;
    return () => {
      addToastExternal = null;
    };
  }, [addToast]);

  const dismiss = (id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <div
      className="pointer-events-none fixed inset-x-0 top-4 z-[60] flex flex-col items-center gap-2 px-4"
      dir="rtl"
    >
      <AnimatePresence>
        {toasts.map((t) => {
          const Icon = ICONS[t.type];
          return (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: -16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.96 }}
              transition={springGentle}
              className="pointer-events-auto flex w-full max-w-sm items-center gap-2.5 rounded-ios-lg border border-separator/40 bg-surface-elevated px-4 py-3 text-callout text-label shadow-ios-lg"
            >
              <Icon className={`h-5 w-5 shrink-0 ${COLORS[t.type]}`} />
              <span className="flex-1">{t.text}</span>
              <button
                onClick={() => dismiss(t.id)}
                className="shrink-0 rounded-full p-0.5 text-label-tertiary transition-colors hover:bg-fill/15 hover:text-label-secondary"
                aria-label="סגור"
              >
                <X size={14} />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
