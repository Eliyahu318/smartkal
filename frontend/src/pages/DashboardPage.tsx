import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import api from "../api/client";
import { useChartColors } from "@/hooks/useChartColors";
import { PageHeader } from "@/components/ui/PageHeader";
import { SegmentedControl } from "@/components/ui/SegmentedControl";

/* ---------- API response types ---------- */

interface CategorySpending {
  category_name: string;
  total: number;
  percentage: number;
}

interface SpendingResponse {
  period: string;
  total_spending: number;
  categories: CategorySpending[];
}

interface StoreSpending {
  store_name: string;
  total: number;
  receipt_count: number;
  percentage: number;
}

interface StoresResponse {
  stores: StoreSpending[];
  total_spending: number;
}

interface MonthTrend {
  month: string;
  total: number;
}

interface TrendsResponse {
  months: MonthTrend[];
}

interface StoreComparisonItem {
  store_name: string;
  total: number;
  matched_count: number;
}

interface CategoryRecommendation {
  category_name: string;
  cheapest_store: string;
  cheapest_total: number;
  savings: number;
}

interface SmartBasketResponse {
  comparisons: StoreComparisonItem[];
  total_items: number;
  matched_items: number;
  cheapest_store: string;
  cheapest_total: number;
  savings: number;
  coverage_text: string;
  category_recommendations: CategoryRecommendation[];
}

/* ---------- Helpers ---------- */

function formatCurrency(value: number): string {
  return `₪${value.toFixed(0)}`;
}

function hebrewMonth(yyyyMm: string): string {
  const [y, m] = yyyyMm.split("-");
  const d = new Date(Number(y), Number(m) - 1);
  return d.toLocaleDateString("he-IL", { month: "short" });
}

/* ---------- Period selector ---------- */

const PERIOD_OPTIONS = [
  { value: "week", label: "שבוע" },
  { value: "month", label: "חודש" },
  { value: "year", label: "שנה" },
] as const;

type Period = (typeof PERIOD_OPTIONS)[number]["value"];

/* ---------- Component ---------- */

export function DashboardPage() {
  const navigate = useNavigate();
  const colors = useChartColors();

  const [period, setPeriod] = useState<Period>("month");
  const [spending, setSpending] = useState<SpendingResponse | null>(null);
  const [stores, setStores] = useState<StoresResponse | null>(null);
  const [trends, setTrends] = useState<TrendsResponse | null>(null);
  const [smartBasket, setSmartBasket] = useState<SmartBasketResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const [spendRes, storesRes, trendsRes, basketRes] = await Promise.allSettled([
          api.get<SpendingResponse>(`/api/v1/dashboard/spending?period=${period}`, { signal }),
          api.get<StoresResponse>("/api/v1/dashboard/stores", { signal }),
          api.get<TrendsResponse>("/api/v1/dashboard/trends", { signal }),
          api.get<SmartBasketResponse>("/api/v1/dashboard/smart-basket", { signal }),
        ]);
        if (signal?.aborted) return;
        if (spendRes.status === "fulfilled") setSpending(spendRes.value.data);
        if (storesRes.status === "fulfilled") setStores(storesRes.value.data);
        if (trendsRes.status === "fulfilled") setTrends(trendsRes.value.data);
        if (basketRes.status === "fulfilled") setSmartBasket(basketRes.value.data);
      } catch {
        if (signal?.aborted) return;
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [period],
  );

  useEffect(() => {
    setLoading(true);
    const controller = new AbortController();
    fetchData(controller.signal);
    return () => controller.abort();
  }, [fetchData]);

  /* ---------- Header ---------- */

  const header = (
    <PageHeader
      title="דשבורד"
      onBack={() => navigate("/more")}
    />
  );

  /* ---------- Loading skeleton ---------- */

  if (loading) {
    return (
      <div>
        {header}
        <div className="space-y-4 px-5 pt-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-48 animate-pulse rounded-ios-lg bg-fill/10"
            />
          ))}
        </div>
      </div>
    );
  }

  const noData =
    !spending?.categories.length && !stores?.stores.length && !trends?.months.length;

  if (noData) {
    return (
      <div>
        {header}
        <div className="mt-20 text-center text-label-tertiary">
          <p className="text-headline">אין נתונים עדיין</p>
          <p className="mt-1 text-subhead">העלה קבלות כדי לראות את הדשבורד</p>
        </div>
      </div>
    );
  }

  /* ---------- Donut chart custom label ---------- */

  const renderLabel = ({
    cx,
    cy,
    midAngle,
    innerRadius,
    outerRadius,
    percentage,
  }: {
    cx: number;
    cy: number;
    midAngle: number;
    innerRadius: number;
    outerRadius: number;
    percentage: number;
  }) => {
    if (percentage < 5) return null;
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);
    return (
      <text
        x={x}
        y={y}
        fill="#fff"
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={12}
      >
        {percentage.toFixed(0)}%
      </text>
    );
  };

  /* ---------- Trend data with Hebrew months ---------- */

  const trendData = (trends?.months ?? []).map((m) => ({
    name: hebrewMonth(m.month),
    total: m.total,
  }));

  // Theme-aware tooltip style for Recharts
  const tooltipStyle = {
    backgroundColor: "rgb(var(--surface-elevated))",
    border: `1px solid ${colors.separator}`,
    borderRadius: "14px",
    direction: "rtl" as const,
    textAlign: "right" as const,
    color: colors.label,
    fontSize: "13px",
    boxShadow: "0 12px 24px -6px rgb(0 0 0 / 0.10)",
  };

  return (
    <div className="pb-8">
      {header}

      {/* Period selector — iOS segmented control */}
      <div className="px-5 pt-2 pb-4">
        <SegmentedControl<Period>
          options={PERIOD_OPTIONS}
          value={period}
          onChange={setPeriod}
          ariaLabel="תקופה"
        />
      </div>

      {/* Total spending card — mint gradient */}
      {spending && (
        <div className="mx-5 rounded-ios-lg bg-gradient-to-l from-brand to-cyan-500 p-5 text-on-brand shadow-ios-md">
          <p className="text-subhead opacity-80">סה״כ הוצאות</p>
          <p className="mt-1 text-largeTitle">
            {formatCurrency(spending.total_spending)}
          </p>
        </div>
      )}

      {/* Smart basket comparison */}
      {smartBasket && smartBasket.comparisons.length > 0 && (
        <div className="mx-5 mt-4 space-y-4">
          {/* Cheapest store recommendation card */}
          <div className="rounded-ios-lg bg-gradient-to-l from-brand via-teal-500 to-cyan-600 p-5 text-on-brand shadow-ios-md">
            <p className="text-subhead opacity-80">הסופר הזול לרשימה שלך</p>
            <p className="mt-1 text-title2">{smartBasket.cheapest_store}</p>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-title3">
                {formatCurrency(smartBasket.cheapest_total)}
              </span>
              {smartBasket.savings > 0 && (
                <span className="rounded-full bg-white/20 px-3 py-0.5 text-subhead font-medium backdrop-blur-sm">
                  חיסכון {formatCurrency(smartBasket.savings)}
                </span>
              )}
            </div>
            {smartBasket.coverage_text && (
              <p className="mt-2 text-caption1 opacity-70">
                {smartBasket.coverage_text}
              </p>
            )}
          </div>

          {/* Per-store price comparison */}
          <div className="rounded-ios-lg bg-surface p-4 shadow-ios-sm">
            <h2 className="mb-3 text-headline text-label">עלות הרשימה לפי חנות</h2>
            <div className="space-y-3">
              {smartBasket.comparisons.map((store) => {
                const isCheapest = store.store_name === smartBasket.cheapest_store;
                const maxTotal =
                  smartBasket.comparisons[smartBasket.comparisons.length - 1]?.total || 1;
                const pct = Math.round((store.total / maxTotal) * 100);
                return (
                  <div key={store.store_name}>
                    <div className="flex items-center justify-between text-subhead">
                      <span
                        className={`font-medium ${
                          isCheapest ? "text-brand" : "text-label"
                        }`}
                      >
                        {isCheapest && (
                          <span className="ml-1 inline-block h-2 w-2 rounded-full bg-brand" />
                        )}
                        {store.store_name}
                      </span>
                      <span className="text-label-secondary/80">
                        {formatCurrency(store.total)} · {store.matched_count} מוצרים
                      </span>
                    </div>
                    <div className="mt-1 h-2 overflow-hidden rounded-full bg-fill/15">
                      <div
                        className={`h-full rounded-full transition-all ${
                          isCheapest ? "bg-brand" : "bg-fill/40"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Per-category store recommendations */}
          {smartBasket.category_recommendations.length > 0 && (
            <div className="rounded-ios-lg bg-surface p-4 shadow-ios-sm">
              <h2 className="mb-3 text-headline text-label">
                החנות הזולה לפי קטגוריה
              </h2>
              <div className="space-y-2">
                {smartBasket.category_recommendations.map((rec) => (
                  <div
                    key={rec.category_name}
                    className="flex items-center justify-between rounded-ios bg-fill/10 px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-subhead font-medium text-label">
                        {rec.category_name}
                      </span>
                      <span className="text-caption1 text-label-tertiary/70">→</span>
                      <span className="text-subhead font-medium text-brand">
                        {rec.cheapest_store}
                      </span>
                    </div>
                    {rec.savings > 0 && (
                      <span className="rounded-full bg-brand/15 px-2 py-0.5 text-caption1 font-medium text-brand">
                        חיסכון {formatCurrency(rec.savings)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Category donut chart */}
      {spending && spending.categories.length > 0 && (
        <div className="mx-5 mt-4 rounded-ios-lg bg-surface p-4 shadow-ios-sm">
          <h2 className="mb-3 text-headline text-label">הוצאות לפי קטגוריה</h2>
          <div className="flex items-center justify-center">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={spending.categories}
                  dataKey="total"
                  nameKey="category_name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={90}
                  paddingAngle={2}
                  label={renderLabel}
                  labelLine={false}
                >
                  {spending.categories.map((_, i) => (
                    <Cell
                      key={i}
                      fill={colors.categorical[i % colors.categorical.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number) => formatCurrency(value)}
                  contentStyle={tooltipStyle}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Legend */}
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5">
            {spending.categories.map((cat, i) => (
              <div
                key={cat.category_name}
                className="flex items-center gap-2 text-subhead"
              >
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{
                    backgroundColor:
                      colors.categorical[i % colors.categorical.length],
                  }}
                />
                <span className="truncate text-label">{cat.category_name}</span>
                <span className="ms-auto text-label-tertiary/70">
                  {cat.percentage.toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Store breakdown */}
      {stores && stores.stores.length > 0 && (
        <div className="mx-5 mt-4 rounded-ios-lg bg-surface p-4 shadow-ios-sm">
          <h2 className="mb-3 text-headline text-label">הוצאות לפי חנות</h2>
          <div className="space-y-3">
            {stores.stores.map((store) => (
              <div key={store.store_name}>
                <div className="flex items-center justify-between text-subhead">
                  <span className="font-medium text-label">
                    {store.store_name}
                  </span>
                  <span className="text-label-secondary/80">
                    {formatCurrency(store.total)} · {store.receipt_count} קבלות
                  </span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-fill/15">
                  <div
                    className="h-full rounded-full bg-brand transition-all"
                    style={{ width: `${store.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Monthly trend chart */}
      {trendData.length > 0 && (
        <div className="mx-5 mt-4 rounded-ios-lg bg-surface p-4 shadow-ios-sm">
          <h2 className="mb-3 text-headline text-label">מגמת הוצאות חודשית</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trendData}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke={colors.grid}
              />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 12, fill: colors.labelSecondary }}
                axisLine={{ stroke: colors.grid }}
                tickLine={{ stroke: colors.grid }}
                reversed
              />
              <YAxis
                tickFormatter={(v: number) => `₪${v}`}
                tick={{ fontSize: 12, fill: colors.labelSecondary }}
                axisLine={{ stroke: colors.grid }}
                tickLine={{ stroke: colors.grid }}
                width={55}
                orientation="right"
              />
              <Tooltip
                formatter={(value: number) => formatCurrency(value)}
                labelStyle={{ direction: "rtl", color: colors.label }}
                contentStyle={tooltipStyle}
              />
              <Line
                type="monotone"
                dataKey="total"
                stroke={colors.brand}
                strokeWidth={2.5}
                dot={{ fill: colors.brand, r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
