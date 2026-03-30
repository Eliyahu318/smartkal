import { useCallback, useEffect, useRef, useState } from "react";
import { ListChecks } from "lucide-react";
import api from "../api/client";
import { AddItemInput } from "../components/AddItemInput";
import { BulkActionBar } from "../components/BulkActionBar";
import { ItemDetailsSheet } from "../components/ItemDetailsSheet";
import { PriceComparisonCard } from "../components/PriceComparisonCard";
import { ShoppingList } from "../components/ShoppingList";
import type { ListItemData, ListResponse } from "../components/ShoppingList";

export function ListPage() {
  const [data, setData] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailsItem, setDetailsItem] = useState<ListItemData | null>(null);
  const refreshedRef = useRef(false);

  // Selection mode state
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const fetchList = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await api.get<ListResponse>("/api/v1/list", { signal });
      setData(res.data);
      setError(null);
    } catch (err) {
      if (signal?.aborted) return;
      setError("שגיאה בטעינת הרשימה");
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function init() {
      // Call refresh on app open (once per mount)
      if (!refreshedRef.current) {
        refreshedRef.current = true;
        try {
          await api.post("/api/v1/list/refresh", null, {
            signal: controller.signal,
          });
        } catch {
          // Refresh is best-effort — don't block list loading
        }
      }
      await fetchList(controller.signal);
    }

    init();
    return () => controller.abort();
  }, [fetchList]);

  const handleToggle = useCallback(async (item: ListItemData) => {
    const endpoint = item.status === "active"
      ? `/api/v1/list/items/${item.id}/complete`
      : `/api/v1/list/items/${item.id}/activate`;

    try {
      await api.patch(endpoint);
      await fetchList();
    } catch {
      setError("שגיאה בעדכון הפריט");
    }
  }, [fetchList]);

  const handleDelete = useCallback(async (item: ListItemData) => {
    try {
      await api.delete(`/api/v1/list/items/${item.id}`);
      await fetchList();
    } catch {
      setError("שגיאה במחיקת הפריט");
    }
  }, [fetchList]);

  const handleLongPress = useCallback((item: ListItemData) => {
    if (selectionMode) return;
    setDetailsItem(item);
  }, [selectionMode]);

  const handleDetailsSaved = useCallback(async () => {
    await fetchList();
  }, [fetchList]);

  const handleItemAdded = useCallback(async () => {
    await fetchList();
  }, [fetchList]);

  // --- Reset all completed items ---
  const handleResetAll = useCallback(async () => {
    try {
      await api.patch("/api/v1/list/items/bulk/activate");
      await fetchList();
    } catch {
      setError("שגיאה באיפוס הפריטים");
    }
  }, [fetchList]);

  // --- Recategorize items in "אחר" ---
  const [recategorizing, setRecategorizing] = useState(false);

  const handleRecategorize = useCallback(async () => {
    setRecategorizing(true);
    try {
      // Process in batches — server handles 30 at a time
      let remaining = 1;
      while (remaining > 0) {
        const { data } = await api.post<{ recategorized_count: number; remaining_count: number }>(
          "/api/v1/list/items/recategorize",
        );
        remaining = data.remaining_count;
        // Refresh list after each batch so user sees progress
        await fetchList();
      }
    } catch {
      setError("שגיאה בסיווג מחדש");
    } finally {
      setRecategorizing(false);
    }
  }, [fetchList]);

  // --- Selection mode ---
  const handleSelectionToggle = useCallback((item: ListItemData) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(item.id)) {
        next.delete(item.id);
      } else {
        next.add(item.id);
      }
      // Exit selection mode if nothing is selected
      if (next.size === 0) {
        setSelectionMode(false);
      }
      return next;
    });
  }, []);

  const enterSelectionMode = useCallback(() => {
    setSelectionMode(true);
    setSelectedIds(new Set());
  }, []);

  const exitSelectionMode = useCallback(() => {
    setSelectionMode(false);
    setSelectedIds(new Set());
  }, []);

  const handleBulkComplete = useCallback(async () => {
    try {
      await api.patch("/api/v1/list/items/bulk/complete", {
        item_ids: [...selectedIds],
      });
      exitSelectionMode();
      await fetchList();
    } catch {
      setError("שגיאה בהשלמת הפריטים");
    }
  }, [selectedIds, exitSelectionMode, fetchList]);

  const handleBulkActivate = useCallback(async () => {
    try {
      await api.patch("/api/v1/list/items/bulk/activate", {
        item_ids: [...selectedIds],
      });
      exitSelectionMode();
      await fetchList();
    } catch {
      setError("שגיאה בהפעלת הפריטים");
    }
  }, [selectedIds, exitSelectionMode, fetchList]);

  const handleBulkDelete = useCallback(async () => {
    try {
      await api.post("/api/v1/list/items/bulk/delete", {
        item_ids: [...selectedIds],
      });
      exitSelectionMode();
      await fetchList();
    } catch {
      setError("שגיאה במחיקת הפריטים");
    }
  }, [selectedIds, exitSelectionMode, fetchList]);

  return (
    <div className="pt-14">
      {/* Header */}
      <div className="flex items-center px-5 pb-3">
        <h1 className="text-2xl font-bold">רשימת קניות</h1>
        <div className="flex-1" />
        {!selectionMode && data && (data.total_active > 0 || data.total_completed > 0) && (
          <button
            type="button"
            onClick={enterSelectionMode}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="בחירה מרובה"
            title="בחירה מרובה"
          >
            <ListChecks className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Price comparison card — hidden when no price data */}
      <PriceComparisonCard />

      {/* Add item input */}
      {!selectionMode && <AddItemInput onItemAdded={handleItemAdded} />}

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-green-500" />
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="px-5 py-4 text-center text-red-500">{error}</p>
      )}

      {/* List */}
      {data && !loading && (
        <ShoppingList
          data={data}
          onToggle={handleToggle}
          onDelete={handleDelete}
          onLongPress={handleLongPress}
          onResetAll={handleResetAll}
          onRecategorize={handleRecategorize}
          recategorizing={recategorizing}
          selectionMode={selectionMode}
          selectedIds={selectedIds}
          onSelectionToggle={handleSelectionToggle}
        />
      )}

      {/* Bulk action bar */}
      {selectionMode && (
        <BulkActionBar
          selectedCount={selectedIds.size}
          onComplete={handleBulkComplete}
          onActivate={handleBulkActivate}
          onDelete={handleBulkDelete}
          onCancel={exitSelectionMode}
        />
      )}

      {/* Item details bottom sheet */}
      <ItemDetailsSheet
        item={detailsItem}
        onClose={() => setDetailsItem(null)}
        onSaved={handleDetailsSaved}
        onDelete={handleDelete}
      />
    </div>
  );
}
