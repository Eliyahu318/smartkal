import { useState } from "react";
import { CategorySection } from "./CategorySection";
import { SwipeableListItem } from "./SwipeableListItem";

// --- Shared types ---

export interface ListItemData {
  id: string;
  name: string;
  quantity: string | null;
  note: string | null;
  status: "active" | "completed";
  category_id: string | null;
  product_id: string | null;
  source: string;
  confidence: number | null;
  display_order: number;
  auto_refresh_days: number | null;
  system_refresh_days: number | null;
  next_refresh_at: string | null;
  last_completed_at: string | null;
  last_activated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CategoryInfo {
  id: string;
  name: string;
  icon: string | null;
  display_order: number;
}

export interface CategoryGroup {
  category: CategoryInfo | null;
  items: ListItemData[];
}

export interface ListResponse {
  groups: CategoryGroup[];
  total_active: number;
  total_completed: number;
}

// --- Component ---

interface ShoppingListProps {
  data: ListResponse;
  onToggle?: (item: ListItemData) => void;
  onDelete?: (item: ListItemData) => void;
  onLongPress?: (item: ListItemData) => void;
  onResetAll?: () => void;
  onRecategorize?: () => void;
  recategorizing?: boolean;
  selectionMode?: boolean;
  selectedIds?: Set<string>;
  onSelectionToggle?: (item: ListItemData) => void;
}

export function ShoppingList({ data, onToggle, onDelete, onLongPress, onResetAll, onRecategorize, recategorizing, selectionMode, selectedIds, onSelectionToggle }: ShoppingListProps) {
  // Separate active and completed groups
  const activeGroups: CategoryGroup[] = [];
  const completedItems: ListItemData[] = [];

  for (const group of data.groups) {
    const active = group.items.filter((i) => i.status === "active");
    const completed = group.items.filter((i) => i.status === "completed");

    if (active.length > 0) {
      activeGroups.push({ ...group, items: active });
    }
    completedItems.push(...completed);
  }

  return (
    <div className="pb-4">
      {/* Active items by category */}
      {activeGroups.map((group) => (
        <CategorySection
          key={group.category?.id ?? "uncategorized"}
          group={group}
          onToggle={onToggle}
          onDelete={onDelete}
          onLongPress={onLongPress}
          selectionMode={selectionMode}
          selectedIds={selectedIds}
          onSelectionToggle={onSelectionToggle}
          onRecategorize={onRecategorize}
          recategorizing={recategorizing}
        />
      ))}

      {/* Empty state */}
      {activeGroups.length === 0 && completedItems.length === 0 && (
        <p data-testid="list-empty-state" className="px-5 pt-4 text-center text-gray-400">
          הרשימה שלך ריקה. הוסיפי מוצר כדי להתחיל!
        </p>
      )}

      {/* Completed section */}
      {completedItems.length > 0 && (
        <CompletedSection
          items={completedItems}
          onToggle={onToggle}
          onDelete={onDelete}
          onLongPress={onLongPress}
          onResetAll={onResetAll}
          selectionMode={selectionMode}
          selectedIds={selectedIds}
          onSelectionToggle={onSelectionToggle}
        />
      )}
    </div>
  );
}

// --- Completed section (collapsed by default) ---

interface CompletedSectionProps {
  items: ListItemData[];
  onToggle?: (item: ListItemData) => void;
  onDelete?: (item: ListItemData) => void;
  onLongPress?: (item: ListItemData) => void;
  onResetAll?: () => void;
  selectionMode?: boolean;
  selectedIds?: Set<string>;
  onSelectionToggle?: (item: ListItemData) => void;
}

function CompletedSection({ items, onToggle, onDelete, onLongPress, onResetAll, selectionMode, selectedIds, onSelectionToggle }: CompletedSectionProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-4 border-t border-gray-100 pt-2">
      <div className="flex items-center px-5 py-2">
        <button
          type="button"
          data-testid="completed-toggle"
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2"
        >
          <span className="text-[13px] font-bold text-gray-400">
            {items.length} הושלמו
          </span>
          <span className="text-[12px] text-gray-400">
            {expanded ? "הסתר" : "הצג"}
          </span>
        </button>

        <div className="flex-1" />

        {onResetAll && items.length > 0 && (
          <button
            type="button"
            onClick={onResetAll}
            className="text-[12px] font-medium text-green-600 hover:text-green-700"
          >
            החזר הכל
          </button>
        )}
      </div>

      {expanded && (
        <div>
          {items.map((item) => (
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
