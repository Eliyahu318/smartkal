import { useRef, useState, useCallback } from "react";
import type { ListItemData } from "./ShoppingList";
import { ListItem } from "./ListItem";

interface SwipeableListItemProps {
  item: ListItemData;
  onToggle?: (item: ListItemData) => void;
  onDelete?: (item: ListItemData) => void;
  onLongPress?: (item: ListItemData) => void;
  selectionMode?: boolean;
  selected?: boolean;
  onSelectionToggle?: (item: ListItemData) => void;
}

const DELETE_THRESHOLD = 80;
const LONG_PRESS_MS = 500;

export function SwipeableListItem({
  item,
  onToggle,
  onDelete,
  onLongPress,
  selectionMode,
  selected,
  onSelectionToggle,
}: SwipeableListItemProps) {
  const [translateX, setTranslateX] = useState(0);
  const [swiping, setSwiping] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const startXRef = useRef(0);
  const currentXRef = useRef(0);
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const didSwipeRef = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const clearLongPress = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  }, []);

  function handleTouchStart(e: React.TouchEvent) {
    if (selectionMode) return;
    const touch = e.touches[0];
    if (!touch) return;
    startXRef.current = touch.clientX;
    currentXRef.current = touch.clientX;
    didSwipeRef.current = false;

    longPressTimer.current = setTimeout(() => {
      if (!didSwipeRef.current) {
        onLongPress?.(item);
      }
    }, LONG_PRESS_MS);
  }

  function handleTouchMove(e: React.TouchEvent) {
    if (selectionMode) return;
    const touch = e.touches[0];
    if (!touch) return;
    currentXRef.current = touch.clientX;
    const deltaX = startXRef.current - touch.clientX;

    if (Math.abs(deltaX) > 10) {
      didSwipeRef.current = true;
      clearLongPress();
    }

    if (deltaX > 0) {
      const capped = Math.min(deltaX, DELETE_THRESHOLD + 20);
      setTranslateX(-capped);
      setSwiping(true);
    } else {
      setTranslateX(0);
    }
  }

  function handleTouchEnd() {
    if (selectionMode) return;
    clearLongPress();

    if (!swiping) {
      setTranslateX(0);
      return;
    }

    const deltaX = startXRef.current - currentXRef.current;

    if (deltaX >= DELETE_THRESHOLD) {
      setTranslateX(-DELETE_THRESHOLD);
    } else {
      setTranslateX(0);
    }
    setSwiping(false);
  }

  function handleDelete() {
    setDeleting(true);
    setTimeout(() => {
      onDelete?.(item);
    }, 250);
  }

  function handleReset() {
    setTranslateX(0);
  }

  // Mouse fallback for desktop (long press only)
  function handleMouseDown() {
    if (selectionMode) return;
    didSwipeRef.current = false;
    longPressTimer.current = setTimeout(() => {
      onLongPress?.(item);
    }, LONG_PRESS_MS);
  }

  function handleMouseUp() {
    clearLongPress();
  }

  // In selection mode, clicking toggles selection
  function handleSelectionClick() {
    if (selectionMode && onSelectionToggle) {
      onSelectionToggle(item);
    }
  }

  return (
    <div
      ref={containerRef}
      className={`relative overflow-hidden transition-all ${
        deleting ? "max-h-0 opacity-0 duration-250" : "max-h-20"
      }`}
      onClick={selectionMode ? handleSelectionClick : undefined}
    >
      {/* Delete button behind */}
      {!selectionMode && (
        <div className="absolute inset-y-0 end-0 flex w-20 items-center justify-center bg-red-500">
          <button
            type="button"
            onClick={handleDelete}
            className="text-[14px] font-semibold text-white"
          >
            הסר
          </button>
        </div>
      )}

      {/* Swipeable content */}
      <div
        className="relative z-10 bg-white"
        style={{
          transform: selectionMode ? undefined : `translateX(${translateX}px)`,
          transition: swiping ? "none" : "transform 200ms ease-out",
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={!selectionMode && translateX !== 0 ? handleReset : undefined}
      >
        <ListItem
          item={item}
          onToggle={selectionMode ? undefined : onToggle}
          onEdit={!selectionMode && onLongPress ? () => onLongPress(item) : undefined}
          selectionMode={selectionMode}
          selected={selected}
        />
      </div>
    </div>
  );
}
