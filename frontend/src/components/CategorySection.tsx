import { useState } from "react";
import { ChevronDown, RefreshCw } from "lucide-react";
import { SwipeableListItem } from "./SwipeableListItem";
import type { CategoryGroup, ListItemData } from "./ShoppingList";

interface CategorySectionProps {
  group: CategoryGroup;
  onToggle?: (item: ListItemData) => void;
  onDelete?: (item: ListItemData) => void;
  onLongPress?: (item: ListItemData) => void;
  selectionMode?: boolean;
  selectedIds?: Set<string>;
  onSelectionToggle?: (item: ListItemData) => void;
  onRecategorize?: () => void;
  recategorizing?: boolean;
}

export function CategorySection({ group, onToggle, onDelete, onLongPress, selectionMode, selectedIds, onSelectionToggle, onRecategorize, recategorizing }: CategorySectionProps) {
  const [collapsed, setCollapsed] = useState(false);
  const label = group.category?.name ?? "ללא קטגוריה";
  const isOther = group.category?.name === "אחר";

  return (
    <div>
      {/* Category header */}
      <div className="flex items-center px-5 py-2">
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2"
        >
          <ChevronDown
            className={`h-4 w-4 text-gray-400 transition-transform ${
              collapsed ? "-rotate-90" : ""
            }`}
          />
          <span className="text-[13px] font-bold uppercase tracking-wide text-gray-500">
            {label}
          </span>
          <span className="text-[12px] text-gray-400">
            {group.items.length}
          </span>
        </button>

        <div className="flex-1" />

        {isOther && onRecategorize && group.items.length > 0 && (
          <button
            type="button"
            onClick={onRecategorize}
            disabled={recategorizing}
            className="flex items-center gap-1 text-[12px] font-medium text-green-600 hover:text-green-700 disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${recategorizing ? "animate-spin" : ""}`} />
            {recategorizing ? "מסווג..." : "סווג מחדש"}
          </button>
        )}
      </div>

      {/* Items */}
      {!collapsed && (
        <div>
          {group.items.map((item) => (
            <SwipeableListItem
              key={item.id}
              item={item}
              onToggle={onToggle}
              onDelete={onDelete}
              onLongPress={onLongPress}
              selectionMode={selectionMode}
              selected={selectedIds?.has(item.id)}
              onSelectionToggle={onSelectionToggle}
            />
          ))}
        </div>
      )}
    </div>
  );
}
