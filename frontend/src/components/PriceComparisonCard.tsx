import { ChevronDown, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import api from "../api/client";

// --- Types ---

interface StoreComparison {
  store_name: string;
  total: number;
  matched_count: number;
}

interface PriceComparisonData {
  comparisons: StoreComparison[];
  total_items: number;
  matched_items: number;
  cheapest_store: string;
  cheapest_total: number;
  current_total: number;
  savings: number;
}

// --- Component ---

export function PriceComparisonCard() {
  const [data, setData] = useState<PriceComparisonData | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchPrices = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await api.get<PriceComparisonData>(
        "/api/v1/prices/compare-list",
        { signal },
      );
      // Only show if there's meaningful data
      if (res.data.comparisons.length > 0 && res.data.savings > 0) {
        setData(res.data);
      }
    } catch {
      // No price data available — card stays hidden
    }
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await api.post("/api/v1/prices/refresh");
      await fetchPrices();
    } catch {
      // Refresh failed silently
    } finally {
      setRefreshing(false);
    }
  }, [fetchPrices]);

  useEffect(() => {
    const controller = new AbortController();
    fetchPrices(controller.signal);
    return () => controller.abort();
  }, [fetchPrices]);

  if (!data) return null;

  const coveragePercent = Math.round(
    (data.matched_items / data.total_items) * 100,
  );

  return (
    <div className="mx-3 mb-3 overflow-hidden rounded-ios-lg border border-brand/20 bg-brand/8 shadow-ios-sm">
      {/* Summary row — always visible */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-3 transition-colors hover:bg-brand/5"
      >
        <div className="flex flex-col items-start gap-0.5">
          <span className="text-footnote font-semibold text-brand">
            הכי זול ב{data.cheapest_store}
          </span>
          <span className="text-caption1 text-label-secondary/80">
            השוואה על {data.matched_items} מתוך {data.total_items} מוצרים ({coveragePercent}%)
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-headline text-brand">
            חיסכון ₪{data.savings.toFixed(2)}
          </span>
          <ChevronDown
            className={`h-4 w-4 text-brand transition-transform ${
              expanded ? "rotate-180" : ""
            }`}
          />
        </div>
      </button>

      {/* Expanded per-store breakdown */}
      {expanded && (
        <div className="border-t border-brand/15 px-4 pb-3 pt-2">
          {data.comparisons.map((store) => {
            const isCheapest = store.store_name === data.cheapest_store;
            return (
              <div
                key={store.store_name}
                className="flex items-center justify-between py-1.5"
              >
                <div className="flex items-center gap-2">
                  {isCheapest && (
                    <span className="h-2 w-2 rounded-full bg-brand" />
                  )}
                  <span
                    className={`text-subhead ${
                      isCheapest
                        ? "font-semibold text-label"
                        : "text-label-secondary"
                    }`}
                  >
                    {store.store_name}
                  </span>
                  <span className="text-caption2 text-label-tertiary/70">
                    ({store.matched_count} מוצרים)
                  </span>
                </div>
                <span
                  className={`text-subhead font-medium ${
                    isCheapest ? "text-brand" : "text-label-secondary"
                  }`}
                >
                  ₪{store.total.toFixed(2)}
                </span>
              </div>
            );
          })}

          {/* Refresh button */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleRefresh();
            }}
            disabled={refreshing}
            className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-ios border border-brand/20 py-2 text-caption1 font-medium text-brand transition-colors hover:bg-brand/10 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "מעדכן מחירים..." : "עדכן מחירים"}
          </button>
        </div>
      )}
    </div>
  );
}
