import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
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

/* ---------- Chart colours ---------- */

const CATEGORY_COLORS = [
  "#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#14b8a6", "#f97316", "#06b6d4", "#84cc16",
  "#a855f7", "#e11d48", "#0ea5e9", "#10b981", "#6366f1",
];

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

const PERIODS = [
  { key: "week", label: "שבוע" },
  { key: "month", label: "חודש" },
  { key: "year", label: "שנה" },
] as const;

/* ---------- Component ---------- */

export function DashboardPage() {
  const navigate = useNavigate();

  const [period, setPeriod] = useState<string>("month");
  const [spending, setSpending] = useState<SpendingResponse | null>(null);
  const [stores, setStores] = useState<StoresResponse | null>(null);
  const [trends, setTrends] = useState<TrendsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const [spendRes, storesRes, trendsRes] = await Promise.all([
          api.get<SpendingResponse>(`/api/v1/dashboard/spending?period=${period}`, { signal }),
          api.get<StoresResponse>("/api/v1/dashboard/stores", { signal }),
          api.get<TrendsResponse>("/api/v1/dashboard/trends", { signal }),
        ]);
        if (signal?.aborted) return;
        setSpending(spendRes.data);
        setStores(storesRes.data);
        setTrends(trendsRes.data);
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

  /* ---------- Back button ---------- */

  const header = (
    <div className="flex items-center gap-2 px-5 pt-14 pb-2">
      <button
        onClick={() => navigate("/more")}
        className="flex items-center gap-1 text-green-600"
      >
        <ChevronRight className="h-5 w-5" />
        <span className="text-sm">עוד</span>
      </button>
      <h1 className="flex-1 text-2xl font-bold">דשבורד הוצאות</h1>
    </div>
  );

  /* ---------- Loading skeleton ---------- */

  if (loading) {
    return (
      <div>
        {header}
        <div className="space-y-4 px-5 pt-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-2xl bg-gray-100" />
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
        <div className="mt-20 text-center text-gray-400">
          <p className="text-lg font-medium">אין נתונים עדיין</p>
          <p className="mt-1 text-sm">העלה קבלות כדי לראות את הדשבורד</p>
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
      <text x={x} y={y} fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={12}>
        {percentage.toFixed(0)}%
      </text>
    );
  };

  /* ---------- Trend data with Hebrew months ---------- */

  const trendData = (trends?.months ?? []).map((m) => ({
    name: hebrewMonth(m.month),
    total: m.total,
  }));

  return (
    <div className="pb-24">
      {header}

      {/* Period selector */}
      <div className="flex gap-2 px-5 pt-2 pb-4">
        {PERIODS.map((p) => (
          <button
            key={p.key}
            onClick={() => setPeriod(p.key)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              period === p.key
                ? "bg-green-600 text-white"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Total spending card */}
      {spending && (
        <div className="mx-5 rounded-2xl bg-gradient-to-l from-green-500 to-green-600 p-5 text-white">
          <p className="text-sm opacity-80">סה״כ הוצאות</p>
          <p className="mt-1 text-3xl font-bold">{formatCurrency(spending.total_spending)}</p>
        </div>
      )}

      {/* Category donut chart */}
      {spending && spending.categories.length > 0 && (
        <div className="mx-5 mt-4 rounded-2xl bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">הוצאות לפי קטגוריה</h2>
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
                    <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number) => formatCurrency(value)}
                  contentStyle={{ direction: "rtl", textAlign: "right" }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Legend */}
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5">
            {spending.categories.map((cat, i) => (
              <div key={cat.category_name} className="flex items-center gap-2 text-sm">
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: CATEGORY_COLORS[i % CATEGORY_COLORS.length] }}
                />
                <span className="truncate text-gray-700">{cat.category_name}</span>
                <span className="ms-auto text-gray-400">{cat.percentage.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Store breakdown */}
      {stores && stores.stores.length > 0 && (
        <div className="mx-5 mt-4 rounded-2xl bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">הוצאות לפי חנות</h2>
          <div className="space-y-3">
            {stores.stores.map((store) => (
              <div key={store.store_name}>
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-gray-800">{store.store_name}</span>
                  <span className="text-gray-500">
                    {formatCurrency(store.total)} · {store.receipt_count} קבלות
                  </span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-green-500 transition-all"
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
        <div className="mx-5 mt-4 rounded-2xl bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold">מגמת הוצאות חודשית</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 12 }}
                reversed
              />
              <YAxis
                tickFormatter={(v: number) => `₪${v}`}
                tick={{ fontSize: 12 }}
                width={55}
                orientation="right"
              />
              <Tooltip
                formatter={(value: number) => formatCurrency(value)}
                labelStyle={{ direction: "rtl" }}
                contentStyle={{ direction: "rtl", textAlign: "right" }}
              />
              <Line
                type="monotone"
                dataKey="total"
                stroke="#22c55e"
                strokeWidth={2.5}
                dot={{ fill: "#22c55e", r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
