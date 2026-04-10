import { useCallback, useEffect, useRef, useState } from "react";
import { Plus } from "lucide-react";
import { motion } from "motion/react";
import { springSnappy, tapScale } from "@/lib/motion";
import api, { getErrorMessageHe } from "../api/client";
import { showToast } from "./Toast";

interface SuggestionItem {
  name: string;
  category_id: string | null;
}

interface AddItemInputProps {
  onItemAdded: () => void;
}

export function AddItemInput({ onItemAdded }: AddItemInputProps) {
  const [value, setValue] = useState("");
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const fetchSuggestions = useCallback(async (query: string) => {
    if (query.length < 1) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    try {
      const res = await api.get<{ suggestions: SuggestionItem[] }>(
        "/api/v1/list/suggestions",
        { params: { q: query } },
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
      inputRef.current?.focus();
    } catch (err) {
      showToast(getErrorMessageHe(err));
    } finally {
      setSubmitting(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      submitItem(value);
    }
  }

  function handleSuggestionClick(suggestion: SuggestionItem) {
    submitItem(suggestion.name, suggestion.category_id);
  }

  // Close suggestions when clicking outside
  useEffect(() => {
    if (!showSuggestions) return;
    function handleClick(e: MouseEvent) {
      if (inputRef.current && !inputRef.current.closest(".add-item-wrapper")?.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showSuggestions]);

  return (
    <div className="add-item-wrapper relative px-4 pb-3">
      <div className="flex items-center gap-2 rounded-ios bg-fill/8 px-3 py-2 transition-colors focus-within:bg-fill/12 focus-within:ring-1 focus-within:ring-brand/30">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="הוסף מוצר..."
          data-testid="add-item-input"
          className="min-w-0 flex-1 bg-transparent text-callout text-label outline-none placeholder:text-label-tertiary/50"
          dir="rtl"
          disabled={submitting}
        />
        <motion.button
          type="button"
          onClick={() => submitItem(value)}
          disabled={!value.trim() || submitting}
          whileTap={tapScale}
          transition={springSnappy}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand transition-opacity disabled:opacity-30"
          aria-label="הוסף"
        >
          <Plus className="h-4 w-4 text-on-brand" />
        </motion.button>
      </div>

      {/* Autocomplete dropdown */}
      {showSuggestions && (
        <div className="absolute start-4 end-4 top-full z-30 mt-1 max-h-48 overflow-y-auto rounded-ios border border-separator/20 bg-surface-elevated shadow-ios-lg">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion.name}
              type="button"
              onClick={() => handleSuggestionClick(suggestion)}
              className="block w-full px-4 py-2.5 text-start text-callout text-label transition-colors hover:bg-fill/10 active:bg-fill/15"
            >
              {suggestion.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
