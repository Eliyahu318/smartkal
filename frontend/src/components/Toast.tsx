import { useEffect, useState, useCallback } from "react";
import { X } from "lucide-react";

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

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 top-4 z-50 flex flex-col items-center gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto flex max-w-sm items-center gap-2 rounded-xl px-4 py-3 text-sm font-medium text-white shadow-lg ${
            t.type === "error"
              ? "bg-red-500"
              : t.type === "success"
                ? "bg-green-500"
                : "bg-gray-700"
          }`}
        >
          <span className="flex-1">{t.text}</span>
          <button
            onClick={() => dismiss(t.id)}
            className="shrink-0 rounded-full p-0.5 hover:bg-white/20"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
