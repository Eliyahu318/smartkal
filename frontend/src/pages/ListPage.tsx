import { useCallback, useEffect, useState } from "react";
import api from "../api/client";
import { ShoppingList } from "../components/ShoppingList";
import type { ListItemData, ListResponse } from "../components/ShoppingList";

export function ListPage() {
  const [data, setData] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    fetchList(controller.signal);
    return () => controller.abort();
  }, [fetchList]);

  const handleToggle = useCallback(async (item: ListItemData) => {
    const endpoint = item.status === "active"
      ? `/api/v1/list/items/${item.id}/complete`
      : `/api/v1/list/items/${item.id}/activate`;

    try {
      await api.patch(endpoint);
      // Re-fetch the full list to get correct groupings
      await fetchList();
    } catch {
      setError("שגיאה בעדכון הפריט");
    }
  }, [fetchList]);

  return (
    <div className="pt-14">
      {/* Header */}
      <div className="px-5 pb-3">
        <h1 className="text-2xl font-bold">רשימת קניות</h1>
      </div>

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
        <ShoppingList data={data} onToggle={handleToggle} />
      )}
    </div>
  );
}
