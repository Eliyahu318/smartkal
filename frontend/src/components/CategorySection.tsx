import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { ListItem } from "./ListItem";
import type { CategoryGroup, ListItemData } from "./ShoppingList";

interface CategorySectionProps {
  group: CategoryGroup;
  onToggle?: (item: ListItemData) => void;
}

export function CategorySection({ group, onToggle }: CategorySectionProps) {
  const [collapsed, setCollapsed] = useState(false);
  const label = group.category?.name ?? "ללא קטגוריה";

  return (
    <div>
      {/* Category header */}
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="flex w-full items-center gap-2 px-5 py-2"
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

      {/* Items */}
      {!collapsed && (
        <div>
          {group.items.map((item) => (
            <ListItem key={item.id} item={item} onToggle={onToggle} />
          ))}
        </div>
      )}
    </div>
  );
}
