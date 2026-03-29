import type { ListItemData } from "./ShoppingList";

interface ListItemProps {
  item: ListItemData;
}

export function ListItem({ item }: ListItemProps) {
  const isCompleted = item.status === "completed";

  return (
    <div className="flex items-center gap-3 px-5 py-2.5">
      {/* Circle indicator */}
      <span
        className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border-2 ${
          isCompleted
            ? "border-green-500 bg-green-500"
            : "border-gray-300 bg-transparent"
        }`}
      >
        {isCompleted && (
          <svg
            className="h-3 w-3 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={3}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        )}
      </span>

      {/* Item content */}
      <div className="min-w-0 flex-1">
        <span
          className={`text-[15px] leading-tight ${
            isCompleted ? "text-gray-400 line-through" : "text-gray-900"
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
