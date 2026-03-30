import { useState } from "react";
import { MoreVertical, Check } from "lucide-react";
import type { ListItemData } from "./ShoppingList";

interface ListItemProps {
  item: ListItemData;
  onToggle?: (item: ListItemData) => void;
  onEdit?: (item: ListItemData) => void;
  selectionMode?: boolean;
  selected?: boolean;
}

export function ListItem({ item, onToggle, onEdit, selectionMode, selected }: ListItemProps) {
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
      } ${selectionMode && selected ? "bg-green-50" : ""}`}
    >
      {/* Selection checkbox or completion circle */}
      {selectionMode ? (
        <div
          className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded border-2 transition-all duration-200 ${
            selected
              ? "border-green-500 bg-green-500"
              : "border-gray-300 bg-transparent"
          }`}
        >
          {selected && <Check className="h-3 w-3 text-white" />}
        </div>
      ) : (
        <button
          type="button"
          onClick={handleToggle}
          className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border-2 transition-all duration-300 ${
            showChecked
              ? "border-green-500 bg-green-500 scale-110"
              : "border-gray-300 bg-transparent scale-100"
          }`}
          aria-label={isCompleted ? "הפעל מחדש" : "סמן כהושלם"}
        >
          <svg
            className={`h-3 w-3 text-white transition-all duration-300 ${
              showChecked ? "opacity-100 scale-100" : "opacity-0 scale-50"
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={3}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </button>
      )}

      {/* Item content */}
      <div className="flex min-w-0 flex-1 items-center gap-1.5">
        {isAutoRefreshed && !isCompleted && (
          <span
            className="inline-block h-2 w-2 shrink-0 rounded-full bg-green-400"
            title="רוענן אוטומטית"
          />
        )}
        <span
          className={`text-[15px] leading-tight transition-all duration-300 ${
            showChecked ? "text-gray-400 line-through" : "text-gray-900"
          }`}
        >
          {item.name}
        </span>
      </div>

      {/* Quantity badge */}
      {item.quantity && (
        <span className="shrink-0 text-[13px] text-gray-400">
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
          className="shrink-0 rounded-full p-1 text-gray-400 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-gray-100 sm:opacity-60"
          aria-label="פרטי פריט"
        >
          <MoreVertical className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
