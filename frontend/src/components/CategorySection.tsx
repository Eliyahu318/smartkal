import { useState } from "react";
import { ChevronDown, RefreshCw } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { SwipeableListItem } from "./SwipeableListItem";
import type { CategoryGroup, ListItemData } from "./ShoppingList";

interface CategorySectionProps {
  group: CategoryGroup;
  onToggle?: (item: ListItemData) => void;
  onDelete?: (item: ListItemData) => void;
  onEdit?: (item: ListItemData) => void;
  selectionMode?: boolean;
  selectedIds?: Set<string>;
  onSelectionToggle?: (item: ListItemData) => void;
  onRecategorize?: () => void;
  recategorizing?: boolean;
}

export function CategorySection({
  group,
  onToggle,
  onDelete,
  onEdit,
  selectionMode,
  selectedIds,
  onSelectionToggle,
  onRecategorize,
  recategorizing,
}: CategorySectionProps) {
  const [collapsed, setCollapsed] = useState(false);
  const label = group.category?.name ?? "ללא קטגוריה";
  const icon = group.category?.icon ?? null;
  const isOther = group.category?.name === "אחר";

  return (
    <section className="mb-4">
      {/* Category header — inset Apple Settings-style label */}
      <div className="flex items-center px-5 pb-1.5 pt-2">
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2"
        >
          <ChevronDown
            className={`h-3.5 w-3.5 text-label-tertiary/70 transition-transform duration-200 ${
              collapsed ? "-rotate-90" : ""
            }`}
          />
          {icon && <span className="text-base leading-none">{icon}</span>}
          <span className="text-footnote font-semibold uppercase tracking-wide text-label-secondary/80">
            {label}
          </span>
          <span className="text-caption1 text-label-tertiary/70">
            {group.items.length}
          </span>
        </button>

        <div className="flex-1" />

        {isOther && onRecategorize && group.items.length > 0 && (
          <button
            type="button"
            onClick={onRecategorize}
            disabled={recategorizing}
            className="flex items-center gap-1 text-caption1 font-medium text-brand transition-colors hover:text-brand-hover disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3 w-3 ${recategorizing ? "animate-spin" : ""}`}
            />
            {recategorizing ? "מסווג..." : "סווג מחדש"}
          </button>
        )}
      </div>

      {/* Items — wrapped in iOS Settings-style grouped card */}
      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }}
            className="overflow-hidden"
          >
            <div className="mx-3 overflow-hidden rounded-ios-lg bg-surface shadow-ios-sm divide-y divide-separator/40">
              {group.items.map((item) => (
                <SwipeableListItem
                  key={item.id}
                  item={item}
                  onToggle={onToggle}
                  onDelete={onDelete}
                  onEdit={onEdit}
                  selectionMode={selectionMode}
                  selected={selectedIds?.has(item.id)}
                  onSelectionToggle={onSelectionToggle}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
