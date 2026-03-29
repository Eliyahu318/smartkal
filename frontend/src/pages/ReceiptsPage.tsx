import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Receipt, FileText, ChevronLeft, ArrowRight, RefreshCw } from "lucide-react";
import api, { getErrorMessageHe } from "../api/client";
import { showToast } from "../components/Toast";
import { ReceiptUpload } from "../components/ReceiptUpload";
import { ReceiptResults } from "../components/ReceiptResults";
import type { UploadResult } from "../components/ReceiptResults";

// --- Types matching backend ReceiptListResponse ---

interface ReceiptSummary {
  id: string;
  store_name: string | null;
  store_branch: string | null;
  receipt_date: string | null;
  total_amount: string | null;
  pdf_filename: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

interface ReceiptListResponse {
  receipts: ReceiptSummary[];
  total: number;
  page: number;
  page_size: number;
}

// --- Helpers ---

function groupByMonth(receipts: ReceiptSummary[]): Map<string, ReceiptSummary[]> {
  const groups = new Map<string, ReceiptSummary[]>();

  for (const r of receipts) {
    const dateStr = r.receipt_date ?? r.created_at;
    const d = new Date(dateStr);
    // Hebrew month-year label
    const key = d.toLocaleDateString("he-IL", {
      month: "long",
      year: "numeric",
    });

    const list = groups.get(key) ?? [];
    list.push(r);
    groups.set(key, list);
  }

  return groups;
}

// --- Skeleton ---

function UploadSkeleton() {
  return (
    <div className="mx-5 space-y-4">
      {/* Receipt header skeleton */}
      <div className="animate-pulse rounded-2xl bg-gray-100 p-4">
        <div className="flex justify-between">
          <div className="space-y-2">
            <div className="h-5 w-32 rounded bg-gray-200" />
            <div className="h-3 w-20 rounded bg-gray-200" />
          </div>
          <div className="h-8 w-20 rounded bg-gray-200" />
        </div>
      </div>

      {/* Match card skeleton */}
      <div className="animate-pulse rounded-2xl bg-green-50 p-4">
        <div className="h-5 w-48 rounded bg-green-100" />
        <div className="mt-2 h-3 w-36 rounded bg-green-100" />
      </div>

      {/* Items skeleton */}
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex animate-pulse items-center gap-3 py-2">
          <div className="h-5 w-5 rounded-full bg-gray-200" />
          <div className="flex-1 space-y-1">
            <div className="h-4 w-40 rounded bg-gray-200" />
            <div className="h-3 w-20 rounded bg-gray-200" />
          </div>
          <div className="h-4 w-14 rounded bg-gray-200" />
        </div>
      ))}
    </div>
  );
}

// --- Receipt history item ---

function ReceiptHistoryItem({
  receipt,
  onClick,
}: {
  receipt: ReceiptSummary;
  onClick: () => void;
}) {
  const dateLabel = receipt.receipt_date
    ? new Date(receipt.receipt_date).toLocaleDateString("he-IL", {
        day: "numeric",
        month: "short",
      })
    : null;

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 px-5 py-3 text-start transition-colors hover:bg-gray-50 active:bg-gray-100"
    >
      <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-gray-100">
        <FileText className="h-5 w-5 text-gray-400" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-800">
          {receipt.store_name ?? "חנות לא ידועה"}
        </p>
        {receipt.store_branch && (
          <p className="truncate text-xs text-gray-400">
            {receipt.store_branch}
          </p>
        )}
      </div>
      <div className="flex-shrink-0 text-left">
        {receipt.total_amount && (
          <p className="text-sm font-medium text-gray-700">
            ₪{receipt.total_amount}
          </p>
        )}
        {dateLabel && <p className="text-xs text-gray-400">{dateLabel}</p>}
      </div>
      <ChevronLeft className="h-4 w-4 flex-shrink-0 text-gray-300" />
    </button>
  );
}

// --- Main page ---

// --- Receipt detail view ---

interface ReceiptDetail {
  id: string;
  store_name: string | null;
  store_branch: string | null;
  receipt_date: string | null;
  total_amount: string | null;
  pdf_filename: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  purchases: Array<{
    id: string;
    raw_name: string;
    quantity: number | null;
    unit_price: string | null;
    total_price: string | null;
    barcode: string | null;
    matched: boolean;
    product_id: string | null;
    created_at: string;
  }>;
}

function ReceiptDetailView({
  receipt,
  onBack,
  onReprocess,
  reprocessing,
}: {
  receipt: ReceiptDetail;
  onBack: () => void;
  onReprocess: () => void;
  reprocessing: boolean;
}) {
  const dateLabel = receipt.receipt_date
    ? new Date(receipt.receipt_date).toLocaleDateString("he-IL", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;

  const matchedCount = receipt.purchases.filter((p) => p.matched).length;
  const unmatchedCount = receipt.purchases.length - matchedCount;

  return (
    <div className="mx-5 space-y-4">
      {/* Back button */}
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1 text-sm font-medium text-green-600"
      >
        <ArrowRight className="h-4 w-4" />
        חזרה לקבלות
      </button>

      {/* Receipt header */}
      <div className="rounded-2xl bg-gray-50 p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-lg font-bold text-gray-900">
              {receipt.store_name ?? "חנות לא ידועה"}
            </p>
            {receipt.store_branch && (
              <p className="text-sm text-gray-500">{receipt.store_branch}</p>
            )}
            {dateLabel && (
              <p className="mt-1 text-xs text-gray-400">{dateLabel}</p>
            )}
          </div>
          {receipt.total_amount && (
            <p className="text-xl font-bold text-gray-900">
              ₪{receipt.total_amount}
            </p>
          )}
        </div>
      </div>

      {/* Match summary */}
      <div className="rounded-2xl bg-green-50 border border-green-200 p-4">
        <p className="text-sm font-medium text-green-800">
          {matchedCount} מוצרים מזוהים · {unmatchedCount} חדשים
        </p>
        <p className="mt-1 text-xs text-green-600">
          {receipt.purchases.length} מוצרים סה״כ
        </p>
      </div>

      {/* Reprocess button */}
      <button
        type="button"
        onClick={onReprocess}
        disabled={reprocessing}
        className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-green-200 bg-white px-4 py-3 text-sm font-semibold text-green-700 transition-all hover:bg-green-50 disabled:opacity-50"
      >
        <RefreshCw className={`h-4 w-4 ${reprocessing ? "animate-spin" : ""}`} />
        {reprocessing ? "מעבד מחדש..." : "עבד מחדש והוסף לרשימה"}
      </button>

      {/* Items list */}
      <div className="space-y-1">
        <p className="text-sm font-semibold text-gray-500">מוצרים</p>
        {receipt.purchases.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-3 rounded-xl py-2"
          >
            <span
              className={`text-sm ${p.matched ? "text-green-500" : "text-orange-400"}`}
            >
              {p.matched ? "✓" : "⚠"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-gray-800">{p.raw_name}</p>
            </div>
            {p.quantity && p.quantity !== 1 && (
              <span className="text-xs text-gray-400">×{p.quantity}</span>
            )}
            {p.total_price && (
              <span className="text-sm font-medium text-gray-600">
                ₪{p.total_price}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}


type PageView = "upload" | "uploading" | "results" | "detail";

export function ReceiptsPage() {
  const navigate = useNavigate();

  // Upload flow state
  const [view, setView] = useState<PageView>("upload");
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [saving, setSaving] = useState(false);

  // Detail view state
  const [selectedReceipt, setSelectedReceipt] = useState<ReceiptDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);

  // Receipt history state
  const [history, setHistory] = useState<ReceiptSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Fetch receipt history
  const fetchHistory = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await api.get<ReceiptListResponse>("/api/v1/receipts", {
        params: { page: 1, page_size: 50 },
        signal,
      });
      setHistory(res.data.receipts);
    } catch (err) {
      if (signal?.aborted) return;
      // Silent fail — history is supplementary
    } finally {
      if (!signal?.aborted) setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchHistory(controller.signal);
    return () => controller.abort();
  }, [fetchHistory]);

  // Handle file upload
  const handleFileSelected = useCallback(async (file: File) => {
    setView("uploading");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await api.post<UploadResult>(
        "/api/v1/receipts/upload",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      setUploadResult(res.data);
      setView("results");
    } catch (err) {
      showToast(getErrorMessageHe(err), "error");
      setView("upload");
    }
  }, []);

  // Handle save — navigate to list tab
  const handleSave = useCallback(async () => {
    setSaving(true);
    // The upload already saved the receipt + purchases + matched list items.
    // "אישור ושמירה" confirms user reviewed the results → navigate to list.
    await fetchHistory();
    setSaving(false);
    navigate("/list");
  }, [navigate, fetchHistory]);

  // Reset to upload view
  const handleNewUpload = useCallback(() => {
    setUploadResult(null);
    setView("upload");
  }, []);

  // Open receipt detail
  const handleReceiptClick = useCallback(async (receiptId: string) => {
    setDetailLoading(true);
    setView("detail");
    try {
      const res = await api.get<ReceiptDetail>(`/api/v1/receipts/${receiptId}`);
      setSelectedReceipt(res.data);
    } catch (err) {
      showToast(getErrorMessageHe(err), "error");
      setView("upload");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // Reprocess receipt — re-run matching and create list items
  const handleReprocess = useCallback(async () => {
    if (!selectedReceipt) return;
    setReprocessing(true);
    try {
      const res = await api.post<UploadResult>(
        `/api/v1/receipts/${selectedReceipt.id}/reprocess`,
      );
      // Update the detail view with fresh data
      setSelectedReceipt(res.data.receipt as unknown as ReceiptDetail);
      const counts = res.data.match_counts;
      if (counts) {
        showToast(
          `${counts.completed_items} פריטים נוספו לרשימה`,
          "success",
        );
      }
    } catch (err) {
      showToast(getErrorMessageHe(err), "error");
    } finally {
      setReprocessing(false);
    }
  }, [selectedReceipt]);

  const monthGroups = groupByMonth(history);

  return (
    <div className="pt-14">
      {/* Header */}
      <div className="flex items-center justify-between px-5 pb-3">
        <h1 className="text-2xl font-bold">קבלות</h1>
        {view === "results" && (
          <button
            type="button"
            onClick={handleNewUpload}
            className="text-sm font-medium text-green-600"
          >
            העלאה חדשה
          </button>
        )}
      </div>

      {/* Upload zone */}
      {view === "upload" && (
        <ReceiptUpload onFileSelected={handleFileSelected} />
      )}

      {/* Loading skeleton */}
      {view === "uploading" && (
        <div data-testid="receipt-uploading">
          <div className="px-5 pb-4">
            <div className="flex items-center gap-2">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-green-500" />
              <p className="text-sm text-gray-500">מנתח את הקבלה...</p>
            </div>
          </div>
          <UploadSkeleton />
        </div>
      )}

      {/* Parsed results */}
      {view === "results" && uploadResult && (
        <ReceiptResults
          result={uploadResult}
          onSave={handleSave}
          saving={saving}
        />
      )}

      {/* Receipt detail view */}
      {view === "detail" && detailLoading && (
        <div className="flex justify-center py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-green-500" />
        </div>
      )}
      {view === "detail" && !detailLoading && selectedReceipt && (
        <ReceiptDetailView
          receipt={selectedReceipt}
          onBack={() => {
            setSelectedReceipt(null);
            setView("upload");
          }}
          onReprocess={handleReprocess}
          reprocessing={reprocessing}
        />
      )}

      {/* Receipt history */}
      {view === "upload" && (
        <div className="mt-6">
          <div className="flex items-center gap-2 px-5 pb-2">
            <Receipt className="h-4 w-4 text-gray-400" />
            <h2 className="text-sm font-semibold text-gray-500">
              היסטוריית קבלות
            </h2>
          </div>

          {historyLoading && (
            <div className="flex justify-center py-8">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-green-500" />
            </div>
          )}

          {!historyLoading && history.length === 0 && (
            <p className="px-5 py-8 text-center text-sm text-gray-400">
              עדיין אין קבלות — העלו את הקבלה הראשונה!
            </p>
          )}

          {!historyLoading &&
            Array.from(monthGroups.entries()).map(([month, receipts]) => (
              <div key={month}>
                <p className="px-5 pb-1 pt-3 text-xs font-medium text-gray-400">
                  {month}
                </p>
                <div className="divide-y divide-gray-100">
                  {receipts.map((r) => (
                    <ReceiptHistoryItem
                      key={r.id}
                      receipt={r}
                      onClick={() => handleReceiptClick(r.id)}
                    />
                  ))}
                </div>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
