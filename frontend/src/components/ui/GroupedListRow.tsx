import type { MouseEventHandler, ReactNode } from "react";
import { ChevronLeft } from "lucide-react";
import { motion } from "motion/react";
import { springSnappy, tapScale } from "@/lib/motion";

interface GroupedListRowProps {
  /** Leading icon (typically a Lucide icon — colored via wrapper) */
  icon?: ReactNode;
  /** Background color class for the icon container (e.g., 'bg-brand/10') */
  iconBg?: string;
  /** Primary label */
  label: ReactNode;
  /** Optional secondary helper text below the label */
  helperText?: ReactNode;
  /** Optional trailing slot — a value, badge, or custom node */
  trailing?: ReactNode;
  /** When true and onClick is set, shows a chevron pointing back (RTL "forward") */
  showChevron?: boolean;
  /** Click handler — when set, the row becomes pressable */
  onClick?: MouseEventHandler<HTMLButtonElement>;
  /** Disable interaction */
  disabled?: boolean;
  /** Make the label use destructive (danger) color — used for logout */
  destructive?: boolean;
  /** Test id for E2E */
  "data-testid"?: string;
}

/**
 * iOS Settings-style row. Used inside <GroupedList>. When onClick is provided,
 * the row becomes a motion.button with tap feedback; otherwise it renders as
 * a static div (for read-only rows like "Version 1.0.0").
 */
export function GroupedListRow({
  icon,
  iconBg = "bg-fill/15",
  label,
  helperText,
  trailing,
  showChevron = false,
  onClick,
  disabled = false,
  destructive = false,
  "data-testid": testId,
}: GroupedListRowProps) {
  const innerContent = (
    <>
      {icon && (
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-ios-sm ${iconBg}`}
        >
          {icon}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div
          className={`text-body ${
            destructive ? "text-danger" : "text-label"
          }`}
        >
          {label}
        </div>
        {helperText && (
          <div className="mt-0.5 text-footnote text-label-tertiary/80">
            {helperText}
          </div>
        )}
      </div>
      {trailing && <div className="flex shrink-0 items-center">{trailing}</div>}
      {showChevron && onClick && (
        <ChevronLeft className="h-4 w-4 shrink-0 text-label-tertiary/60" />
      )}
    </>
  );

  const baseClasses =
    "flex w-full items-center gap-3 px-4 py-3.5 text-right text-body";

  if (onClick && !disabled) {
    return (
      <motion.button
        type="button"
        onClick={onClick}
        whileTap={tapScale}
        transition={springSnappy}
        data-testid={testId}
        className={`${baseClasses} bg-surface transition-colors hover:bg-fill/5 active:bg-fill/10`}
      >
        {innerContent}
      </motion.button>
    );
  }

  if (onClick && disabled) {
    return (
      <button
        type="button"
        disabled
        data-testid={testId}
        className={`${baseClasses} bg-surface opacity-50`}
      >
        {innerContent}
      </button>
    );
  }

  return (
    <div data-testid={testId} className={`${baseClasses} bg-surface`}>
      {innerContent}
    </div>
  );
}
