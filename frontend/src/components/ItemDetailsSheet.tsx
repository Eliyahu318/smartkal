import { useState, useEffect, useCallback } from "react";
import { X } from "lucide-react";
import type { ListItemData } from "./ShoppingList";
import api from "../api/client";

interface ItemDetailsSheetProps {
  item: ListItemData | null;
  onClose: () => void;
  onSaved: () => void;
}

export function ItemDetailsSheet({ item, onClose, onSaved }: ItemDetailsSheetProps) {
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [refreshDays, setRefreshDays] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (item) {
      setQuantity(item.quantity ?? "");
      setNote(item.note ?? "");
      setRefreshDays(item.auto_refresh_days?.toString() ?? "");
    }
  }, [item]);

  const handleSave = useCallback(async () => {
    if (!item) return;
    setSaving(true);

    try {
      // Update item details (quantity + note)
      const hasItemChanges =
        quantity !== (item.quantity ?? "") || note !== (item.note ?? "");

      if (hasItemChanges) {
        await api.put(`/api/v1/list/items/${item.id}`, {
          name: item.name,
          quantity: quantity || null,
          note: note || null,
        });
      }

      // Update frequency preference if changed
      const newRefreshDays = refreshDays ? parseInt(refreshDays, 10) : null;
      if (newRefreshDays !== item.auto_refresh_days) {
        await api.patch(`/api/v1/list/items/${item.id}/preferences`, {
          auto_refresh_days: newRefreshDays,
        });
      }

      onSaved();
      onClose();
    } catch {
      // Error handled by interceptor toast
    } finally {
      setSaving(false);
    }
  }, [item, quantity, note, refreshDays, onSaved, onClose]);

  // Handle backdrop click
  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  if (!item) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center"
      onClick={handleBackdropClick}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" />

      {/* Sheet */}
      <div
        className="relative w-full max-w-[430px] rounded-t-2xl bg-white px-5 pb-8 pt-4 animate-slide-up"
        dir="rtl"
      >
        {/* Handle + close */}
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-gray-900">{item.name}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1 text-gray-400 hover:bg-gray-100"
            aria-label="סגור"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form fields */}
        <div className="space-y-4">
          {/* Quantity */}
          <div>
            <label className="mb-1 block text-[13px] font-medium text-gray-500">
              כמות
            </label>
            <input
              type="text"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="לדוגמה: 2, 500 גרם"
              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 text-[15px] outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500"
              dir="rtl"
            />
          </div>

          {/* Note */}
          <div>
            <label className="mb-1 block text-[13px] font-medium text-gray-500">
              הערה
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="הערה לפריט..."
              rows={2}
              className="w-full resize-none rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 text-[15px] outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500"
              dir="rtl"
            />
          </div>

          {/* Refresh frequency override */}
          <div>
            <label className="mb-1 block text-[13px] font-medium text-gray-500">
              תדירות רענון (ימים)
            </label>
            <input
              type="number"
              inputMode="numeric"
              value={refreshDays}
              onChange={(e) => setRefreshDays(e.target.value)}
              placeholder={
                item.system_refresh_days
                  ? `מחושב: כל ${item.system_refresh_days} ימים`
                  : "לא מוגדר"
              }
              min={1}
              max={365}
              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 text-[15px] outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500"
              dir="rtl"
            />
            {item.system_refresh_days && !refreshDays && (
              <p className="mt-1 text-[12px] text-gray-400">
                המערכת חישבה כל {item.system_refresh_days} ימים
              </p>
            )}
          </div>
        </div>

        {/* Save button */}
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="mt-6 w-full rounded-xl bg-green-500 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-green-600 disabled:opacity-50"
        >
          {saving ? "שומר..." : "שמור"}
        </button>
      </div>
    </div>
  );
}
