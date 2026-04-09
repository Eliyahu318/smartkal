import { useState, useEffect, useCallback } from "react";
import { Trash2 } from "lucide-react";
import type { ListItemData } from "./ShoppingList";
import api from "../api/client";
import { Sheet } from "./ui/Sheet";
import { IOSButton } from "./ui/IOSButton";

interface ItemDetailsSheetProps {
  item: ListItemData | null;
  onClose: () => void;
  onSaved: () => void;
  onDelete?: (item: ListItemData) => void;
}

export function ItemDetailsSheet({
  item,
  onClose,
  onSaved,
  onDelete,
}: ItemDetailsSheetProps) {
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [refreshDays, setRefreshDays] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (item) {
      setName(item.name);
      setQuantity(item.quantity ?? "");
      setNote(item.note ?? "");
      setRefreshDays(item.auto_refresh_days?.toString() ?? "");
    }
  }, [item]);

  const handleSave = useCallback(async () => {
    if (!item) return;
    setSaving(true);

    try {
      // Update item details (name + quantity + note)
      const hasItemChanges =
        name !== item.name ||
        quantity !== (item.quantity ?? "") ||
        note !== (item.note ?? "");

      if (hasItemChanges) {
        await api.put(`/api/v1/list/items/${item.id}`, {
          name: name.trim() || item.name,
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
  }, [item, name, quantity, note, refreshDays, onSaved, onClose]);

  const handleDelete = useCallback(() => {
    if (!item || !onDelete) return;
    onDelete(item);
    onClose();
  }, [item, onDelete, onClose]);

  return (
    <Sheet open={!!item} onClose={onClose} ariaLabel="פרטי פריט">
      <div className="px-5 pb-6 pt-2">
        {/* Form fields */}
        <div className="space-y-4">
          {/* Name (editable) */}
          <div>
            <label className="mb-1 block text-footnote font-medium text-label-secondary/80">
              שם מוצר
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-ios border border-separator/40 bg-fill/10 px-3 py-2.5 text-callout font-bold text-label outline-none transition-colors focus:border-brand focus:bg-surface focus:ring-1 focus:ring-brand"
              dir="rtl"
            />
          </div>

          {/* Quantity */}
          <div>
            <label className="mb-1 block text-footnote font-medium text-label-secondary/80">
              כמות
            </label>
            <input
              type="text"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="לדוגמה: 2, 500 גרם"
              className="w-full rounded-ios border border-separator/40 bg-fill/10 px-3 py-2.5 text-callout text-label outline-none transition-colors placeholder:text-label-tertiary/60 focus:border-brand focus:bg-surface focus:ring-1 focus:ring-brand"
              dir="rtl"
            />
          </div>

          {/* Note */}
          <div>
            <label className="mb-1 block text-footnote font-medium text-label-secondary/80">
              הערה
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="הערה לפריט..."
              rows={2}
              className="w-full resize-none rounded-ios border border-separator/40 bg-fill/10 px-3 py-2.5 text-callout text-label outline-none transition-colors placeholder:text-label-tertiary/60 focus:border-brand focus:bg-surface focus:ring-1 focus:ring-brand"
              dir="rtl"
            />
          </div>

          {/* Refresh frequency override */}
          <div>
            <label className="mb-1 block text-footnote font-medium text-label-secondary/80">
              תדירות רענון (ימים)
            </label>
            <input
              type="number"
              inputMode="numeric"
              value={refreshDays}
              onChange={(e) => setRefreshDays(e.target.value)}
              placeholder={
                item?.system_refresh_days
                  ? `מחושב: כל ${item.system_refresh_days} ימים`
                  : "לא מוגדר"
              }
              min={1}
              max={365}
              className="w-full rounded-ios border border-separator/40 bg-fill/10 px-3 py-2.5 text-callout text-label outline-none transition-colors placeholder:text-label-tertiary/60 focus:border-brand focus:bg-surface focus:ring-1 focus:ring-brand"
              dir="rtl"
            />
            {item?.system_refresh_days && !refreshDays && (
              <p className="mt-1 text-caption1 text-label-tertiary/70">
                המערכת חישבה כל {item.system_refresh_days} ימים
              </p>
            )}
          </div>
        </div>

        {/* Save button */}
        <IOSButton
          variant="filled"
          size="lg"
          fullWidth
          onClick={handleSave}
          disabled={saving}
          className="mt-6"
        >
          {saving ? "שומר..." : "שמור"}
        </IOSButton>

        {/* Delete button */}
        {onDelete && (
          <IOSButton
            variant="destructive-tinted"
            size="lg"
            fullWidth
            onClick={handleDelete}
            className="mt-3"
          >
            <Trash2 className="h-4 w-4" />
            מחק פריט
          </IOSButton>
        )}
      </div>
    </Sheet>
  );
}
