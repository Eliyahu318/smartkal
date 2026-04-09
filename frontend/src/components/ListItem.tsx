import { useState } from "react";
import { MoreVertical, Check } from "lucide-react";
import { motion } from "motion/react";
import { springSnappy } from "@/lib/motion";
import type { ListItemData } from "./ShoppingList";

interface ListItemProps {
  item: ListItemData;
  onToggle?: (item: ListItemData) => void;
  onEdit?: (item: ListItemData) => void;
  selectionMode?: boolean;
  selected?: boolean;
}

export function ListItem({
  item,
  onToggle,
  onEdit,
  selectionMode,
  selected,
}: ListItemProps) {
  const isCompleted = item.status === "completed";
  const isAutoRefreshed = item.source === "auto_refresh";
  const [animating, setAnimating] = useState(false);

  function handleToggle() {
    if (!onToggle || selectionMode) return;
    setAnimating(true);
    setTimeout(() => {
      onToggle(item);
      setAnimating(false);
    }, 300);
  }

  const showChecked = animating ? !isCompleted : isCompleted;

  return (
    <div
      className={`group flex items-center gap-3 px-5 py-2.5 transition-opacity duration-300 ${
        animating ? "opacity-60" : "opacity-100"
      } ${selectionMode && selected ? "bg-brand/10" : ""}`}
    >
      {/* Selection checkbox or completion circle */}
      {selectionMode ? (
        <div
          className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-md border-2 transition-all duration-200 ${
            selected
              ? "border-brand bg-brand"
              : "border-separator-opaque bg-transparent"
          }`}
        >
          {selected && <Check className="h-3 w-3 text-on-brand" />}
        </div>
      ) : (
        <motion.button
          type="button"
          onClick={handleToggle}
          whileTap={{ scale: 0.9 }}
          transition={springSnappy}
          className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border-2 transition-all duration-300 ${
            showChecked
              ? "scale-110 border-brand bg-brand"
              : "scale-100 border-separator-opaque bg-transparent"
          }`}
          aria-label={isCompleted ? "הפעל מחדש" : "סמן כהושלם"}
        >
          {/* SF-style animated check draw using SVG pathLength */}
          <svg
            className="h-3 w-3"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={3}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <motion.path
              d="M5 13l4 4L19 7"
              className="text-on-brand"
              initial={false}
              animate={{
                pathLength: showChecked ? 1 : 0,
                opacity: showChecked ? 1 : 0,
              }}
              transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
            />
          </svg>
        </motion.button>
      )}

      {/* Item content */}
      <div className="flex min-w-0 flex-1 items-center gap-1.5">
        {isAutoRefreshed && !isCompleted && (
          <span
            className="inline-block h-2 w-2 shrink-0 rounded-full bg-brand"
            title="רוענן אוטומטית"
          />
        )}
        <span
          className={`text-callout leading-tight transition-all duration-300 ${
            showChecked
              ? "text-label-tertiary line-through"
              : "text-label"
          }`}
        >
          {item.name}
        </span>
      </div>

      {/* Quantity badge */}
      {item.quantity && (
        <span className="shrink-0 text-footnote text-label-tertiary">
          {item.quantity}
        </span>
      )}

      {/* Edit button — visible on hover (desktop), hidden in selection mode */}
      {onEdit && !selectionMode && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onEdit(item);
          }}
          className="shrink-0 rounded-full p-1 text-label-tertiary opacity-0 transition-opacity hover:bg-fill/10 group-hover:opacity-100 sm:opacity-60"
          aria-label="פרטי פריט"
        >
          <MoreVertical className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
