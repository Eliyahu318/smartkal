/**
 * Shared motion variants and transitions used across the iOS-style UI.
 *
 * Centralized so every interactive element feels consistent — same spring
 * curves, same enter/exit timings, same tap-feedback scale.
 */
import type { Transition, Variants } from "motion/react";

// ---------- Springs ----------

/** Gentle spring — used for layout shifts, sheet transitions, page transitions */
export const springGentle: Transition = {
  type: "spring",
  stiffness: 300,
  damping: 30,
  mass: 1,
};

/** Snappy spring — used for tap feedback, swipe-back, active-state changes */
export const springSnappy: Transition = {
  type: "spring",
  stiffness: 400,
  damping: 35,
  mass: 0.8,
};

// ---------- Tap feedback ----------

/** Apple-standard "press in" scale — pair with motion.button whileTap */
export const tapScale = { scale: 0.97 };

// ---------- Page transitions ----------

/**
 * Page transition variants — used by AppShell's AnimatePresence wrapper.
 * Subtle cross-fade with a tiny horizontal shift, RTL-aware via the negative x.
 */
export const pageVariants: Variants = {
  initial: { opacity: 0, x: -8 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 8 },
};

export const pageTransition: Transition = {
  duration: 0.22,
  ease: [0.32, 0.72, 0, 1], // iOS standard cubic-bezier
};

// ---------- Sheet transitions ----------

/** Bottom sheet enter/exit — used by Sheet primitive and ItemDetailsSheet */
export const sheetVariants: Variants = {
  initial: { y: "100%", opacity: 0 },
  animate: { y: 0, opacity: 1 },
  exit: { y: "100%", opacity: 0 },
};

// ---------- List item enter/exit ----------

/** Used for items animating in/out of a list (e.g. delete, add, merge) */
export const listItemVariants: Variants = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95, height: 0 },
};
