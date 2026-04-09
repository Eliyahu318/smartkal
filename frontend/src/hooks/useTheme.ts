import { useThemeStore } from "@/store/themeStore";

/**
 * Convenience hook for components that need to read or change the theme.
 * Returns a stable selector subset of the theme store.
 */
export function useTheme() {
  const theme = useThemeStore((s) => s.theme);
  const resolved = useThemeStore((s) => s.resolved);
  const setTheme = useThemeStore((s) => s.setTheme);
  return { theme, resolved, setTheme };
}
