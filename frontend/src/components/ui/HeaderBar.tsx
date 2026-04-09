import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";
import { motion } from "motion/react";
import { springSnappy, tapScale } from "@/lib/motion";

interface HeaderBarProps {
  /** Page title — typically text-largeTitle for top-level pages */
  title?: ReactNode;
  /** Optional subtitle below the title */
  subtitle?: ReactNode;
  /** When set, shows a back button (RTL: ArrowRight points back) and calls onBack */
  onBack?: () => void;
  /** Custom leading slot — overrides the back button if provided */
  leading?: ReactNode;
  /** Trailing slot — typically action buttons */
  trailing?: ReactNode;
  /** When true, renders the title in a smaller size (use for nested pages) */
  compact?: boolean;
  /** Test id for E2E */
  "data-testid"?: string;
}

/**
 * Shared page header. Provides consistent top spacing (pt-14 for status-bar
 * clearance), back button affordance, title typography, and trailing actions.
 *
 * Pages that hand-roll their own header today are migrated to use this.
 */
export function HeaderBar({
  title,
  subtitle,
  onBack,
  leading,
  trailing,
  compact = false,
  "data-testid": testId,
}: HeaderBarProps) {
  return (
    <header
      data-testid={testId}
      className="flex items-start gap-2 px-5 pb-3 pt-14"
    >
      {/* Leading slot — custom > back button > nothing */}
      {leading
        ? leading
        : onBack && (
            <motion.button
              type="button"
              onClick={onBack}
              whileTap={tapScale}
              transition={springSnappy}
              aria-label="חזרה"
              className="-mr-1.5 mt-1 rounded-ios-sm p-1.5 text-label-tertiary transition-colors hover:bg-fill/10 hover:text-label-secondary"
            >
              <ArrowRight className="h-5 w-5" />
            </motion.button>
          )}

      {/* Title block */}
      <div className="min-w-0 flex-1">
        {title && (
          <h1
            className={`text-label ${
              compact ? "text-title2" : "text-largeTitle"
            }`}
          >
            {title}
          </h1>
        )}
        {subtitle && (
          <p className="mt-0.5 text-subhead text-label-secondary/80">
            {subtitle}
          </p>
        )}
      </div>

      {/* Trailing slot */}
      {trailing && <div className="mt-1 flex shrink-0 items-center gap-1">{trailing}</div>}
    </header>
  );
}
