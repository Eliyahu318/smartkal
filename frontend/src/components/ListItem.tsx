import { useState } from "react";
import type { ListItemData } from "./ShoppingList";

interface ListItemProps {
  item: ListItemData;
  onToggle?: (item: ListItemData) => void;
}

export function ListItem({ item, onToggle }: ListItemProps) {
  const isCompleted = item.status === "completed";
  // Local animation state: when user taps, we animate immediately (optimistic)
  const [animating, setAnimating] = useState(false);

  function handleToggle() {
    if (!onToggle) return;
    setAnimating(true);
    // Let the CSS transition play, then fire the callback
    setTimeout(() => {
      onToggle(item);
      setAnimating(false);
    }, 300);
  }

  // Show as "checked" if completed and not animating, or if active and animating (optimistic flip)
  const showChecked = animating ? !isCompleted : isCompleted;

  return (
    <div
      className={`flex items-center gap-3 px-5 py-2.5 transition-opacity duration-300 ${
        animating ? "opacity-60" : "opacity-100"
      }`}
    >
      {/* Circle indicator — tappable */}
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

      {/* Item content */}
      <div className="min-w-0 flex-1">
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
    </div>
  );
}
