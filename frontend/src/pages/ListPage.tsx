import { useEffect, useState } from "react";
import api from "../api/client";
import { ShoppingList } from "../components/ShoppingList";
import type { ListResponse } from "../components/ShoppingList";

export function ListPage() {
  const [data, setData] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchList() {
      try {
        const res = await api.get<ListResponse>("/api/v1/list");
        if (!cancelled) {
          setData(res.data);
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setError("שגיאה בטעינת הרשימה");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchList();
    return () => { cancelled = true; };
  }, []);

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
      {data && !loading && <ShoppingList data={data} />}
    </div>
  );
}
