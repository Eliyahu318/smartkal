import { create } from "zustand";

// ---------- Types ----------
export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

interface ThemeState {
  /** User's theme preference (persisted to localStorage) */
  theme: ThemePreference;
  /** The actual theme currently applied (computed from `theme` + system pref) */
  resolved: ResolvedTheme;

  /** Update the user's theme preference and apply it immediately */
  setTheme: (theme: ThemePreference) => void;
  /** Initialize on app boot — read localStorage, attach system listener */
  init: () => void;
}

// ---------- Constants ----------
const STORAGE_KEY = "smartkal-theme";
const LIGHT_THEME_COLOR = "#00C7BE"; // iOS Mint
const DARK_THEME_COLOR = "#1c1c1e"; // iOS dark surface

// ---------- Helpers ----------
function readStoredTheme(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // localStorage access can throw in some sandboxed contexts
  }
  return "system";
}

function systemPrefersDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function computeResolved(theme: ThemePreference): ResolvedTheme {
  if (theme === "system") return systemPrefersDark() ? "dark" : "light";
  return theme;
}

function applyTheme(resolved: ResolvedTheme): void {
  if (typeof document === "undefined") return;

  // Toggle the .dark class on <html> — Tailwind reads this for darkMode: 'class'
  if (resolved === "dark") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }

  // Update the active <meta name="theme-color"> for browser chrome.
  // We have two metas (one per prefers-color-scheme); the browser auto-picks
  // based on system preference, but we override here so manual user choice wins.
  // Strategy: set a single dynamic meta if it doesn't exist; remove the
  // media-scoped ones the first time the user makes an explicit choice.
  const dynamicMeta = document.querySelector<HTMLMetaElement>(
    'meta[name="theme-color"]:not([media])',
  );
  const color = resolved === "dark" ? DARK_THEME_COLOR : LIGHT_THEME_COLOR;

  if (dynamicMeta) {
    dynamicMeta.content = color;
  } else {
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    meta.content = color;
    document.head.appendChild(meta);
  }
}

function persistTheme(theme: ThemePreference): void {
  try {
    if (theme === "system") {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, theme);
    }
  } catch {
    // localStorage may throw — non-fatal, just lose persistence for this session
  }
}

// ---------- Store ----------
export const useThemeStore = create<ThemeState>((set, get) => {
  let mediaQuery: MediaQueryList | null = null;
  let mediaListener: ((e: MediaQueryListEvent) => void) | null = null;

  return {
    theme: "system",
    resolved: "light",

    setTheme: (theme) => {
      const resolved = computeResolved(theme);
      persistTheme(theme);
      applyTheme(resolved);
      set({ theme, resolved });
    },

    init: () => {
      const theme = readStoredTheme();
      const resolved = computeResolved(theme);
      // The FOUC-prevention script in index.html already added/removed .dark
      // synchronously. applyTheme() here re-syncs in case localStorage and the
      // class are out of step (rare, but defensive).
      applyTheme(resolved);
      set({ theme, resolved });

      // Listen to system preference changes — only react when user is on "system"
      if (typeof window !== "undefined" && window.matchMedia) {
        mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        mediaListener = (e) => {
          if (get().theme !== "system") return;
          const newResolved: ResolvedTheme = e.matches ? "dark" : "light";
          applyTheme(newResolved);
          set({ resolved: newResolved });
        };
        // Modern browsers — addEventListener is the standard
        mediaQuery.addEventListener("change", mediaListener);
      }
    },
  };
});
