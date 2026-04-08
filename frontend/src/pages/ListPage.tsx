import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckSquare, GitMerge, ListChecks, X } from "lucide-react";
import { Link } from "react-router-dom";
import api, { getErrorMessageHe } from "../api/client";
import { AddItemInput } from "../components/AddItemInput";
import { BulkActionBar } from "../components/BulkActionBar";
import { ItemDetailsSheet } from "../components/ItemDetailsSheet";
import { PriceComparisonCard } from "../components/PriceComparisonCard";
import { ShoppingList } from "../components/ShoppingList";
import type { ListItemData, ListResponse } from "../components/ShoppingList";
import { showToast } from "../components/Toast";
import type { DuplicatesResponse } from "../types/duplicates";

export function ListPage() {
  const [data, setData] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailsItem, setDetailsItem] = useState<ListItemData | null>(null);
  const refreshedRef = useRef(false);

  // Selection mode state
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Duplicate detection — fetched alongside the list, shown as a header badge
  const [duplicateGroupCount, setDuplicateGroupCount] = useState<number>(0);

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

  const fetchDuplicates = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await api.get<DuplicatesResponse>("/api/v1/list/duplicates", {
        signal,
      });
      setDuplicateGroupCount(res.data.groups.length);
    } catch {
      // Silent — duplicate detection is best-effort and shouldn't block the list
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
      // Check for duplicates after the list is loaded — must run AFTER fetchList
      // so the lazy backfill of canonical_key has had a chance to run.
      await fetchDuplicates(controller.signal);
    }

    init();
    return () => controller.abort();
  }, [fetchList, fetchDuplicates]);

  const handleToggle = useCallback(async (item: ListItemData) => {
    const endpoint = item.status === "active"
      ? `/api/v1/list/items/${item.id}/complete`
      : `/api/v1/list/items/${item.id}/activate`;

    try {
      await api.patch(endpoint);
      await fetchList();
    } catch (err) {
      setError(getErrorMessageHe(err));
    }
  }, [fetchList]);

  const handleDelete = useCallback(async (item: ListItemData) => {
    try {
      await api.delete(`/api/v1/list/items/${item.id}`);
      await fetchList();
    } catch (err) {
      setError(getErrorMessageHe(err));
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
    } catch (err) {
      setError(getErrorMessageHe(err));
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
    } catch (err) {
      setError(getErrorMessageHe(err));
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
    } catch (err) {
      setError(getErrorMessageHe(err));
    }
  }, [selectedIds, exitSelectionMode, fetchList]);

  const handleBulkActivate = useCallback(async () => {
    try {
      await api.patch("/api/v1/list/items/bulk/activate", {
        item_ids: [...selectedIds],
      });
      exitSelectionMode();
      await fetchList();
    } catch (err) {
      setError(getErrorMessageHe(err));
    }
  }, [selectedIds, exitSelectionMode, fetchList]);

  const handleBulkDelete = useCallback(async () => {
    try {
      await api.post("/api/v1/list/items/bulk/delete", {
        item_ids: [...selectedIds],
      });
      exitSelectionMode();
      await fetchList();
    } catch (err) {
      setError(getErrorMessageHe(err));
    }
  }, [selectedIds, exitSelectionMode, fetchList]);

  // Collect all active item IDs for "select all"
  const allActiveIds = useMemo(() => {
    if (!data) return new Set<string>();
    const ids = new Set<string>();
    for (const group of data.groups) {
      for (const item of group.items) {
        if (item.status === "active") {
          ids.add(item.id);
        }
      }
    }
    return ids;
  }, [data]);

  const allSelected = allActiveIds.size > 0 && selectedIds.size >= allActiveIds.size;

  const handleSelectAll = useCallback(() => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(allActiveIds));
    }
  }, [allSelected, allActiveIds]);

  const handleBulkMerge = useCallback(async () => {
    if (selectedIds.size < 2) return;
    const ids = [...selectedIds];
    // Pick the first selected as the target — keeps it deterministic and lets the
    // user pre-select the item they want to keep first.
    const [targetId, ...sourceIds] = ids;
    if (!targetId || sourceIds.length === 0) return;
    try {
      await api.post("/api/v1/list/merge", {
        target_id: targetId,
        source_ids: sourceIds,
      });
      showToast(`${sourceIds.length + 1} פריטים אוחדו`, "success");
      exitSelectionMode();
      await fetchList();
      await fetchDuplicates();
    } catch (err) {
      showToast(getErrorMessageHe(err));
    }
  }, [selectedIds, exitSelectionMode, fetchList, fetchDuplicates]);

  return (
    <div className="pt-14">
      {/* Header */}
      <div className="flex items-center px-5 pb-3">
        {selectionMode ? (
          <>
            <button
              type="button"
              onClick={exitSelectionMode}
              className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              aria-label="ביטול בחירה"
            >
              <X className="h-5 w-5" />
            </button>
            <span className="mr-2 text-sm font-medium text-gray-500">
              {selectedIds.size > 0 ? `${selectedIds.size} נבחרו` : "בחר פריטים"}
            </span>
            <div className="flex-1" />
            <button
              type="button"
              onClick={handleSelectAll}
              className={`rounded-lg p-1.5 transition-colors ${
                allSelected
                  ? "text-green-600 hover:bg-green-50"
                  : "text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              }`}
              aria-label={allSelected ? "בטל בחירת הכל" : "בחר הכל"}
              title={allSelected ? "בטל בחירת הכל" : "בחר הכל"}
            >
              <CheckSquare className="h-5 w-5" />
            </button>
          </>
        ) : (
          <>
            <h1 className="text-2xl font-bold">רשימת קניות</h1>
            <div className="flex-1" />
            {data && (data.total_active > 0 || data.total_completed > 0) && (
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
          </>
        )}
      </div>

      {/* Duplicates badge — surfaces if the dedup engine found candidate groups */}
      {!selectionMode && duplicateGroupCount > 0 && (
        <div className="px-5 pb-3">
          <Link
            to="/duplicates"
            className="flex items-center gap-2 rounded-xl border border-purple-200 bg-purple-50 px-3 py-2 text-sm font-medium text-purple-800 hover:bg-purple-100"
          >
            <GitMerge className="h-4 w-4" />
            <span>נמצאו {duplicateGroupCount} קבוצות כפילויות — לחץ לאיחוד</span>
          </Link>
        </div>
      )}

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
          onMerge={handleBulkMerge}
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
