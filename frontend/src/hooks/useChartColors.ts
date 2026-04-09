import { useEffect, useState } from "react";
import { useThemeStore } from "@/store/themeStore";

interface ChartColors {
  brand: string;
  label: string;
  labelSecondary: string;
  grid: string;
  separator: string;
  /** iOS-inspired categorical palette for category breakdowns */
  categorical: string[];
}

/**
 * Reads CSS variables defined in :root / .dark and converts them to rgb(...)
 * strings that Recharts can consume directly. Re-runs whenever the theme
 * changes so charts repaint with the correct colors.
 *
 * Recharts has no native CSS-var support — props must be JS strings — so this
 * bridge is mandatory for theme-aware charts.
 */
export function useChartColors(): ChartColors {
  const resolved = useThemeStore((s) => s.resolved);
  const [colors, setColors] = useState<ChartColors>(() => readColors());

  useEffect(() => {
    setColors(readColors());
  }, [resolved]);

  return colors;
}

function readColors(): ChartColors {
  if (typeof document === "undefined") {
    // SSR fallback (not used in this app, but defensive)
    return {
      brand: "rgb(0, 199, 190)",
      label: "rgb(0, 0, 0)",
      labelSecondary: "rgb(60, 60, 67)",
      grid: "rgb(60, 60, 67)",
      separator: "rgb(60, 60, 67)",
      categorical: [
        "#00C7BE",
        "#5856D6",
        "#FF9F0A",
        "#FF375F",
        "#30D158",
        "#64D2FF",
      ],
    };
  }

  const styles = getComputedStyle(document.documentElement);
  const rgb = (varName: string): string => {
    const triple = styles.getPropertyValue(varName).trim();
    return triple ? `rgb(${triple.split(/\s+/).join(",")})` : "rgb(0,0,0)";
  };
  const rgba = (varName: string, alpha: number): string => {
    const triple = styles.getPropertyValue(varName).trim();
    return triple
      ? `rgba(${triple.split(/\s+/).join(",")},${alpha})`
      : `rgba(0,0,0,${alpha})`;
  };

  return {
    brand: rgb("--brand"),
    label: rgb("--label"),
    labelSecondary: rgba("--label-secondary", 0.6),
    grid: rgba("--separator", 0.18),
    separator: rgba("--separator", 0.4),
    // Stable categorical palette — same in both themes for chart consistency.
    // These are iOS system colors at full saturation.
    categorical: [
      "#00C7BE", // Mint (brand)
      "#5856D6", // Indigo
      "#FF9F0A", // Orange
      "#FF375F", // Pink
      "#30D158", // Green
      "#64D2FF", // Light blue
      "#BF5AF2", // Purple
      "#FFD60A", // Yellow
    ],
  };
}
