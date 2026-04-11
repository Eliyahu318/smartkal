import { useRef, useState } from "react";
import type { ListItemData } from "./ShoppingList";
import { ListItem } from "./ListItem";

interface SwipeableListItemProps {
  item: ListItemData;
  onToggle?: (item: ListItemData) => void;
  onDelete?: (item: ListItemData) => void;
  /** Opens the full details sheet (MoreVertical button). */
  onEdit?: (item: ListItemData) => void;
  /** Inline rename — fired after double-tap edit is committed. */
  onRename?: (item: ListItemData, newName: string) => void;
  selectionMode?: boolean;
  selected?: boolean;
  onSelectionToggle?: (item: ListItemData) => void;
}

const DELETE_THRESHOLD = 80;
// Max ms between two taps to count as a double-tap.
const DOUBLE_TAP_MS = 300;
// Movement threshold before we decide whether the gesture is a horizontal
// swipe or a vertical scroll. Below this, we don't commit to a direction.
const DIRECTION_LOCK_PX = 8;

type ScrollLock = "none" | "horizontal" | "vertical";

export function SwipeableListItem({
  item,
  onToggle,
  onDelete,
  onEdit,
  onRename,
  selectionMode,
  selected,
  onSelectionToggle,
}: SwipeableListItemProps) {
  const [translateX, setTranslateX] = useState(0);
  const [swiping, setSwiping] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [editing, setEditing] = useState(false);

  const startXRef = useRef(0);
  const startYRef = useRef(0);
  const currentXRef = useRef(0);
  const scrollLockRef = useRef<ScrollLock>("none");
  const lastTapRef = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);

  function handleTouchStart(e: React.TouchEvent) {
    if (selectionMode || editing) return;
    const touch = e.touches[0];
    if (!touch) return;
    startXRef.current = touch.clientX;
    startYRef.current = touch.clientY;
    currentXRef.current = touch.clientX;
    scrollLockRef.current = "none";
  }

  function handleTouchMove(e: React.TouchEvent) {
    if (selectionMode || editing) return;
    const touch = e.touches[0];
    if (!touch) return;
    currentXRef.current = touch.clientX;

    const deltaX = startXRef.current - touch.clientX;
    const deltaY = touch.clientY - startYRef.current;

    // Decide once per gesture whether the user is swiping horizontally or
    // scrolling vertically. Without this, a fast vertical scroll that has
    // any tiny horizontal component would briefly reveal the red delete
    // button before snapping back.
    if (scrollLockRef.current === "none") {
      if (Math.hypot(deltaX, deltaY) < DIRECTION_LOCK_PX) return;
      scrollLockRef.current =
        Math.abs(deltaY) > Math.abs(deltaX) ? "vertical" : "horizontal";
    }

    if (scrollLockRef.current === "vertical") {
      // Let the browser scroll; don't touch the transform.
      return;
    }

    // Horizontal swipe — only reveal the delete button when swiping left
    // (deltaX > 0 in the current refs; content moves in -X direction, which
    // in RTL exposes the delete action on the end side).
    if (deltaX > 0) {
      const capped = Math.min(deltaX, DELETE_THRESHOLD + 20);
      setTranslateX(-capped);
      setSwiping(true);
    } else {
      setTranslateX(0);
    }
  }

  function handleTouchEnd(e: React.TouchEvent) {
    if (selectionMode || editing) return;

    const wasHorizontal = scrollLockRef.current === "horizontal";
    scrollLockRef.current = "none";

    if (!swiping) {
      setTranslateX(0);
      // Double-tap detection — only if this wasn't a swipe or vertical scroll.
      if (!wasHorizontal) {
        const now = Date.now();
        if (now - lastTapRef.current < DOUBLE_TAP_MS) {
          // Suppress the synthesized click / text-selection callout.
          e.preventDefault();
          lastTapRef.current = 0;
          setEditing(true);
          return;
        }
        lastTapRef.current = now;
      } else {
        lastTapRef.current = 0;
      }
      return;
    }

    const deltaX = startXRef.current - currentXRef.current;

    if (deltaX >= DELETE_THRESHOLD) {
      setTranslateX(-DELETE_THRESHOLD);
    } else {
      setTranslateX(0);
    }
    setSwiping(false);
    lastTapRef.current = 0;
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

  function handleDoubleClick() {
    if (selectionMode) return;
    setEditing(true);
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
      className={`relative overflow-hidden transition-all duration-300 ease-out ${
        deleting ? "max-h-0 opacity-0" : "max-h-20"
      }`}
      onClick={selectionMode ? handleSelectionClick : undefined}
    >
      {/* Delete button behind */}
      {!selectionMode && (
        <div className="absolute inset-y-0 end-0 flex w-20 items-center justify-center bg-danger">
          <button
            type="button"
            onClick={handleDelete}
            className="text-footnote font-semibold text-white"
          >
            הסר
          </button>
        </div>
      )}

      {/* Swipeable content */}
      <div
        className={`relative z-10 bg-surface ${editing ? "" : "select-none [-webkit-touch-callout:none] [-webkit-user-select:none]"}`}
        style={{
          transform: selectionMode ? undefined : `translateX(${translateX}px)`,
          transition: swiping ? "none" : "transform 200ms cubic-bezier(0.32, 0.72, 0, 1)",
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onDoubleClick={handleDoubleClick}
        onClick={!selectionMode && translateX !== 0 ? handleReset : undefined}
      >
        <ListItem
          item={item}
          onToggle={selectionMode ? undefined : onToggle}
          onEdit={!selectionMode && onEdit ? () => onEdit(item) : undefined}
          selectionMode={selectionMode}
          selected={selected}
          editing={editing}
          onCancelEdit={() => setEditing(false)}
          onCommitRename={(newName) => {
            setEditing(false);
            onRename?.(item, newName);
          }}
        />
      </div>
    </div>
  );
}
