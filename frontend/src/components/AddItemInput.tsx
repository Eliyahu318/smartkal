import { useCallback, useEffect, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import api from "../api/client";

interface SuggestionItem {
  name: string;
  category_id: string | null;
}

interface AddItemInputProps {
  onItemAdded: () => void;
}

export function AddItemInput({ onItemAdded }: AddItemInputProps) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Focus input when opened
  useEffect(() => {
    if (open) {
      // Small delay to let animation complete
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const fetchSuggestions = useCallback(async (query: string) => {
    if (query.length < 1) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    try {
      const res = await api.get<{ suggestions: SuggestionItem[] }>(
        "/api/v1/list/suggestions",
        { params: { q: query } }
      );
      setSuggestions(res.data.suggestions);
      setShowSuggestions(res.data.suggestions.length > 0);
    } catch {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }, []);

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value;
    setValue(val);

    // Debounce autocomplete requests
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchSuggestions(val.trim());
    }, 200);
  }

  async function submitItem(name: string, categoryId?: string | null) {
    const trimmed = name.trim();
    if (!trimmed || submitting) return;

    setSubmitting(true);
    setShowSuggestions(false);

    try {
      await api.post("/api/v1/list/items", {
        name: trimmed,
        ...(categoryId ? { category_id: categoryId } : {}),
      });
      setValue("");
      setSuggestions([]);
      onItemAdded();
      // Keep input open for adding more items
      inputRef.current?.focus();
    } catch {
      // Error handled by Axios interceptor (toast)
    } finally {
      setSubmitting(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      submitItem(value);
    } else if (e.key === "Escape") {
      handleClose();
    }
  }

  function handleSuggestionClick(suggestion: SuggestionItem) {
    submitItem(suggestion.name, suggestion.category_id);
  }

  function handleClose() {
    setOpen(false);
    setValue("");
    setSuggestions([]);
    setShowSuggestions(false);
  }

  // FAB button when closed
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-24 left-1/2 z-30 flex h-12 w-12 -translate-x-1/2 items-center justify-center rounded-full bg-green-500 shadow-lg transition-transform active:scale-95 sm:absolute"
        aria-label="הוסף מוצר"
      >
        <Plus className="h-6 w-6 text-white" />
      </button>
    );
  }

  // Inline input when open
  return (
    <div className="sticky top-0 z-20 bg-white px-4 pb-2 pt-2 shadow-sm">
      <div className="relative">
        <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2">
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="הוסף מוצר..."
            className="min-w-0 flex-1 bg-transparent text-[15px] text-gray-900 outline-none placeholder:text-gray-400"
            dir="rtl"
            disabled={submitting}
          />
          {value.trim() ? (
            <button
              type="button"
              onClick={() => submitItem(value)}
              disabled={submitting}
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-green-500 transition-opacity disabled:opacity-50"
              aria-label="הוסף"
            >
              <Plus className="h-4 w-4 text-white" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleClose}
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-200"
              aria-label="סגור"
            >
              <X className="h-4 w-4 text-gray-500" />
            </button>
          )}
        </div>

        {/* Autocomplete dropdown */}
        {showSuggestions && (
          <div className="absolute start-0 end-0 top-full z-30 mt-1 max-h-48 overflow-y-auto rounded-xl border border-gray-100 bg-white shadow-lg">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion.name}
                type="button"
                onClick={() => handleSuggestionClick(suggestion)}
                className="block w-full px-4 py-2.5 text-start text-[14px] text-gray-800 transition-colors hover:bg-gray-50 active:bg-gray-100"
              >
                {suggestion.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
