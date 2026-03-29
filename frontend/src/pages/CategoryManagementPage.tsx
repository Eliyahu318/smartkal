import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronRight,
  GripVertical,
  Pencil,
  Plus,
  Trash2,
  Check,
  X,
} from "lucide-react";
import api from "@/api/client";
import { showToast } from "@/components/Toast";

interface Category {
  id: string;
  name: string;
  icon: string | null;
  display_order: number;
  is_default: boolean;
}

export function CategoryManagementPage() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);

  // Inline editing
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const editInputRef = useRef<HTMLInputElement>(null);

  // Add new category
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState("");
  const addInputRef = useRef<HTMLInputElement>(null);

  // Drag reorder state
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await api.get<Category[]>("/api/v1/categories");
      setCategories(res.data);
    } catch {
      showToast("שגיאה בטעינת קטגוריות");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCategories();
  }, [fetchCategories]);

  // Focus input when editing starts
  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);

  useEffect(() => {
    if (showAdd && addInputRef.current) {
      addInputRef.current.focus();
    }
  }, [showAdd]);

  // --- Rename ---
  const startEdit = (cat: Category) => {
    setEditingId(cat.id);
    setEditName(cat.name);
  };

  const confirmEdit = async () => {
    if (!editingId || !editName.trim()) {
      setEditingId(null);
      return;
    }
    try {
      await api.put(`/api/v1/categories/${editingId}`, {
        name: editName.trim(),
      });
      setCategories((prev) =>
        prev.map((c) =>
          c.id === editingId ? { ...c, name: editName.trim() } : c,
        ),
      );
      showToast("הקטגוריה עודכנה", "success");
    } catch {
      showToast("שגיאה בעדכון קטגוריה");
    }
    setEditingId(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  // --- Add ---
  const confirmAdd = async () => {
    if (!newName.trim()) {
      setShowAdd(false);
      return;
    }
    try {
      const res = await api.post<Category>("/api/v1/categories", {
        name: newName.trim(),
      });
      setCategories((prev) => [...prev, res.data]);
      setNewName("");
      setShowAdd(false);
      showToast("הקטגוריה נוספה", "success");
    } catch {
      showToast("שגיאה בהוספת קטגוריה");
    }
  };

  // --- Delete ---
  const handleDelete = async (cat: Category) => {
    if (cat.name === "אחר") return;
    const confirmed = window.confirm(
      `למחוק את "${cat.name}"? הפריטים יועברו ל"אחר".`,
    );
    if (!confirmed) return;

    try {
      await api.delete(`/api/v1/categories/${cat.id}`);
      setCategories((prev) => prev.filter((c) => c.id !== cat.id));
      showToast("הקטגוריה נמחקה", "success");
    } catch {
      showToast("שגיאה במחיקת קטגוריה");
    }
  };

  // --- Drag reorder ---
  const handleDragStart = (idx: number) => {
    setDragIdx(idx);
  };

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    setOverIdx(idx);
  };

  const handleDrop = async () => {
    if (dragIdx === null || overIdx === null || dragIdx === overIdx) {
      setDragIdx(null);
      setOverIdx(null);
      return;
    }

    const reordered = [...categories];
    const moved = reordered.splice(dragIdx, 1)[0];
    if (!moved) return;
    reordered.splice(overIdx, 0, moved);
    setCategories(reordered);
    setDragIdx(null);
    setOverIdx(null);

    try {
      await api.post("/api/v1/categories/reorder", {
        category_ids: reordered.map((c) => c.id),
      });
    } catch {
      showToast("שגיאה בשינוי סדר");
      void fetchCategories();
    }
  };

  const handleDragEnd = () => {
    setDragIdx(null);
    setOverIdx(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center pt-32">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-green-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="px-5 pt-14 pb-8">
      {/* Header */}
      <button
        onClick={() => navigate("/more")}
        className="mb-4 flex items-center gap-1 text-sm text-green-600"
      >
        <ChevronRight className="h-4 w-4" />
        <span>חזרה</span>
      </button>

      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">ניהול קטגוריות</h1>
          <p className="mt-1 text-sm text-gray-500">
            שנה שם, סדר מחדש, או מחק קטגוריות
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-green-500 text-white shadow-sm active:bg-green-600"
        >
          <Plus className="h-5 w-5" />
        </button>
      </div>

      {/* Add new category inline */}
      {showAdd && (
        <div className="mb-3 flex items-center gap-2 rounded-xl bg-white px-4 py-3 shadow-sm">
          <input
            ref={addInputRef}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void confirmAdd();
              if (e.key === "Escape") setShowAdd(false);
            }}
            placeholder="שם קטגוריה חדשה..."
            className="flex-1 text-[15px] outline-none placeholder:text-gray-300"
          />
          <button
            onClick={() => void confirmAdd()}
            className="rounded-lg p-1.5 text-green-600 active:bg-green-50"
          >
            <Check className="h-5 w-5" />
          </button>
          <button
            onClick={() => {
              setShowAdd(false);
              setNewName("");
            }}
            className="rounded-lg p-1.5 text-gray-400 active:bg-gray-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      )}

      {/* Category list */}
      <div className="space-y-1">
        {categories.map((cat, idx) => (
          <div
            key={cat.id}
            draggable
            onDragStart={() => handleDragStart(idx)}
            onDragOver={(e) => handleDragOver(e, idx)}
            onDrop={() => void handleDrop()}
            onDragEnd={handleDragEnd}
            className={`flex items-center gap-2 rounded-xl bg-white px-3 py-3 shadow-sm transition-opacity ${
              dragIdx === idx ? "opacity-50" : ""
            } ${overIdx === idx && dragIdx !== idx ? "ring-2 ring-green-300" : ""}`}
          >
            {/* Drag handle */}
            <span className="cursor-grab touch-none text-gray-300 active:cursor-grabbing">
              <GripVertical className="h-5 w-5" />
            </span>

            {/* Icon */}
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-50 text-base">
              {cat.icon ?? "📁"}
            </span>

            {/* Name / edit input */}
            {editingId === cat.id ? (
              <input
                ref={editInputRef}
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void confirmEdit();
                  if (e.key === "Escape") cancelEdit();
                }}
                onBlur={() => void confirmEdit()}
                className="flex-1 rounded-lg border border-green-300 px-2 py-1 text-[15px] outline-none"
              />
            ) : (
              <span className="flex-1 text-[15px] font-medium text-gray-800">
                {cat.name}
              </span>
            )}

            {/* Actions */}
            {editingId !== cat.id && (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => startEdit(cat)}
                  className="rounded-lg p-1.5 text-gray-400 active:bg-gray-50"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                {cat.name !== "אחר" && (
                  <button
                    onClick={() => void handleDelete(cat)}
                    className="rounded-lg p-1.5 text-red-400 active:bg-red-50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {categories.length === 0 && (
        <div className="mt-12 text-center text-sm text-gray-400">
          אין קטגוריות — הוסף קטגוריה חדשה
        </div>
      )}
    </div>
  );
}
