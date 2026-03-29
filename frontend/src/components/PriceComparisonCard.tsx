import { ChevronDown } from "lucide-react";
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
    <div className="mx-5 mb-3 overflow-hidden rounded-xl bg-green-50 border border-green-200">
      {/* Summary row — always visible */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-3"
      >
        <div className="flex flex-col items-start gap-0.5">
          <span className="text-[13px] font-semibold text-green-800">
            הכי זול ב{data.cheapest_store}
          </span>
          <span className="text-[12px] text-green-600">
            השוואה על {data.matched_items} מתוך {data.total_items} מוצרים ({coveragePercent}%)
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[17px] font-bold text-green-700">
            חיסכון ₪{data.savings.toFixed(2)}
          </span>
          <ChevronDown
            className={`h-4 w-4 text-green-600 transition-transform ${
              expanded ? "rotate-180" : ""
            }`}
          />
        </div>
      </button>

      {/* Expanded per-store breakdown */}
      {expanded && (
        <div className="border-t border-green-200 px-4 pb-3 pt-2">
          {data.comparisons.map((store) => {
            const isCheapest = store.store_name === data.cheapest_store;
            return (
              <div
                key={store.store_name}
                className="flex items-center justify-between py-1.5"
              >
                <div className="flex items-center gap-2">
                  {isCheapest && (
                    <span className="h-2 w-2 rounded-full bg-green-500" />
                  )}
                  <span
                    className={`text-[14px] ${
                      isCheapest
                        ? "font-semibold text-green-800"
                        : "text-gray-700"
                    }`}
                  >
                    {store.store_name}
                  </span>
                  <span className="text-[11px] text-gray-400">
                    ({store.matched_count} מוצרים)
                  </span>
                </div>
                <span
                  className={`text-[14px] font-medium ${
                    isCheapest ? "text-green-700" : "text-gray-600"
                  }`}
                >
                  ₪{store.total.toFixed(2)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
