import { useState } from "react";
import {
  ChevronDown,
  AlertTriangle,
  Check,
  Trash2,
  ShoppingCart,
} from "lucide-react";

// --- Types matching backend UploadReceiptResponse ---

export interface PurchaseData {
  id: string;
  raw_name: string;
  quantity: number | null;
  unit_price: string | null; // Decimal from backend
  total_price: string | null;
  barcode: string | null;
  matched: boolean;
  product_id: string | null;
  created_at: string;
}

export interface ReceiptData {
  id: string;
  store_name: string | null;
  store_branch: string | null;
  receipt_date: string | null;
  total_amount: string | null;
  pdf_filename: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  purchases: PurchaseData[];
}

export interface MatchCounts {
  barcode: number;
  exact_name: number;
  fuzzy: number;
  new: number;
  completed_items: number;
  auto_merged_to_existing?: number;
  completed_via_alias?: number;
}

export interface UploadResult {
  receipt: ReceiptData;
  parsed_item_count: number;
  match_counts: MatchCounts | null;
}

interface ReceiptResultsProps {
  result: UploadResult;
  onSave: () => void;
  saving?: boolean;
}

// --- Category breakdown helper ---

interface CategoryBreakdown {
  name: string;
  count: number;
  total: number;
}

function buildCategoryBreakdown(purchases: PurchaseData[]): CategoryBreakdown[] {
  // Group matched vs unmatched since we don't have category info from the receipt API
  const matched = purchases.filter((p) => p.matched);
  const unmatched = purchases.filter((p) => !p.matched);

  const groups: CategoryBreakdown[] = [];
  if (matched.length > 0) {
    groups.push({
      name: "מוצרים מזוהים",
      count: matched.length,
      total: matched.reduce(
        (sum, p) => sum + (p.total_price ? parseFloat(p.total_price) : 0),
        0,
      ),
    });
  }
  if (unmatched.length > 0) {
    groups.push({
      name: "מוצרים חדשים",
      count: unmatched.length,
      total: unmatched.reduce(
        (sum, p) => sum + (p.total_price ? parseFloat(p.total_price) : 0),
        0,
      ),
    });
  }
  return groups;
}

// --- Sub-components ---

function MatchSummaryCard({ counts }: { counts: MatchCounts }) {
  const totalMatched = counts.barcode + counts.exact_name + counts.fuzzy;
  const total = totalMatched + counts.new;
  const autoMerged = counts.auto_merged_to_existing ?? 0;

  return (
    <div className="mx-5 rounded-2xl bg-green-50 p-4">
      <div className="flex items-center gap-2 text-green-700">
        <ShoppingCart className="h-5 w-5" />
        <span className="text-lg font-bold">
          {counts.completed_items} פריטים הושלמו ברשימה
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-green-600">
        {counts.barcode > 0 && <span>ברקוד: {counts.barcode}</span>}
        {counts.exact_name > 0 && <span>שם מדויק: {counts.exact_name}</span>}
        {counts.fuzzy > 0 && <span>התאמה חכמה: {counts.fuzzy}</span>}
      </div>
      {autoMerged > 0 && (
        <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-cyan-100 px-2.5 py-1 text-xs font-medium text-cyan-800">
          <span>{autoMerged} פריטים אוחדו אוטומטית עם פריטים קיימים</span>
        </div>
      )}
      {counts.new > 0 && (
        <p className="mt-2 text-sm text-gray-500">
          {counts.new} מוצרים חדשים נוספו מתוך {total} סה&quot;כ
        </p>
      )}
    </div>
  );
}

function CategoryBreakdownSection({
  breakdown,
}: {
  breakdown: CategoryBreakdown[];
}) {
  const [open, setOpen] = useState(false);

  if (breakdown.length === 0) return null;

  return (
    <div className="mx-5">
      <button
        type="button"
        className="flex w-full items-center justify-between py-2"
        onClick={() => setOpen(!open)}
      >
        <span className="text-sm font-semibold text-gray-700">
          פירוט לפי קטגוריה
        </span>
        <ChevronDown
          className={`h-4 w-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="space-y-2 pb-3">
          {breakdown.map((cat) => (
            <div
              key={cat.name}
              className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2"
            >
              <span className="text-sm text-gray-600">
                {cat.name} ({cat.count})
              </span>
              <span className="text-sm font-medium">
                ₪{cat.total.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PurchaseItem({
  purchase,
  onDelete,
}: {
  purchase: PurchaseData;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-3 px-5 py-2.5">
      <div
        className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full ${
          purchase.matched
            ? "bg-green-100 text-green-600"
            : "bg-orange-100 text-orange-500"
        }`}
      >
        {purchase.matched ? (
          <Check className="h-3 w-3" />
        ) : (
          <AlertTriangle className="h-3 w-3" />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-gray-800">{purchase.raw_name}</p>
        <div className="flex gap-2 text-xs text-gray-400">
          {purchase.quantity != null && <span>×{purchase.quantity}</span>}
          {purchase.unit_price && <span>₪{purchase.unit_price}/יח&apos;</span>}
        </div>
      </div>

      <span className="flex-shrink-0 text-sm font-medium text-gray-700">
        {purchase.total_price ? `₪${purchase.total_price}` : "—"}
      </span>

      <button
        type="button"
        onClick={() => onDelete(purchase.id)}
        className="flex-shrink-0 rounded-full p-1 text-gray-300 transition-colors hover:bg-red-50 hover:text-red-400"
        aria-label="מחק פריט"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

// --- Main component ---

export function ReceiptResults({ result, onSave, saving }: ReceiptResultsProps) {
  const [purchases, setPurchases] = useState<PurchaseData[]>(
    result.receipt.purchases,
  );

  const handleDeletePurchase = (id: string) => {
    setPurchases((prev) => prev.filter((p) => p.id !== id));
  };

  const totalAmount = result.receipt.total_amount;
  const storeName = result.receipt.store_name;
  const storeBranch = result.receipt.store_branch;
  const receiptDate = result.receipt.receipt_date;
  const unmatched = purchases.filter((p) => !p.matched);
  const breakdown = buildCategoryBreakdown(purchases);

  return (
    <div className="space-y-4 pb-6">
      {/* Receipt header */}
      <div className="mx-5 rounded-2xl bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-bold text-gray-800">
              {storeName ?? "חנות לא ידועה"}
            </h3>
            {storeBranch && (
              <p className="text-sm text-gray-500">{storeBranch}</p>
            )}
            {receiptDate && (
              <p className="text-xs text-gray-400">{receiptDate}</p>
            )}
          </div>
          {totalAmount && (
            <div className="text-left">
              <p className="text-2xl font-bold text-green-600">
                ₪{totalAmount}
              </p>
              <p className="text-xs text-gray-400">סה&quot;כ</p>
            </div>
          )}
        </div>
      </div>

      {/* Match summary */}
      {result.match_counts && <MatchSummaryCard counts={result.match_counts} />}

      {/* Unmatched items warning */}
      {unmatched.length > 0 && (
        <div className="mx-5 flex items-center gap-2 rounded-xl bg-orange-50 px-4 py-3">
          <AlertTriangle className="h-4 w-4 flex-shrink-0 text-orange-500" />
          <p className="text-sm text-orange-700">
            {unmatched.length} מוצרים לא זוהו — יתווספו כמוצרים חדשים
          </p>
        </div>
      )}

      {/* Category breakdown */}
      <CategoryBreakdownSection breakdown={breakdown} />

      {/* Parsed items list */}
      <div>
        <h4 className="px-5 pb-2 text-sm font-semibold text-gray-700">
          פריטים ({purchases.length})
        </h4>
        <div className="divide-y divide-gray-100">
          {purchases.map((purchase) => (
            <PurchaseItem
              key={purchase.id}
              purchase={purchase}
              onDelete={handleDeletePurchase}
            />
          ))}
        </div>
      </div>

      {/* Save button */}
      <div className="px-5 pt-2">
        <button
          type="button"
          data-testid="receipt-save"
          onClick={onSave}
          disabled={saving || purchases.length === 0}
          className="w-full rounded-xl bg-green-500 py-3.5 text-base font-bold text-white transition-colors hover:bg-green-600 disabled:opacity-50"
        >
          {saving ? (
            <span className="flex items-center justify-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              שומר...
            </span>
          ) : (
            "אישור ושמירה"
          )}
        </button>
      </div>
    </div>
  );
}
