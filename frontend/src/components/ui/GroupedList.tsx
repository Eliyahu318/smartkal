import type { ReactNode } from "react";

interface GroupedListProps {
  /** Optional inset section header — Apple Settings-style uppercase footnote */
  header?: ReactNode;
  /** Optional inset section footer (helper text below the card) */
  footer?: ReactNode;
  /** Rows of the grouped list — usually GroupedListRow children */
  children: ReactNode;
  className?: string;
}

/**
 * iOS Settings-style grouped list. Renders a rounded card with internal
 * separator hairlines (handled by `divide-y divide-separator` on the inner
 * container). Use multiple GroupedList instances on a page to create the
 * Settings-app stacked-section look.
 */
export function GroupedList({
  header,
  footer,
  children,
  className = "",
}: GroupedListProps) {
  return (
    <div className={`mb-6 ${className}`}>
      {header && (
        <div className="px-4 pb-2 pt-1 text-footnote uppercase tracking-wide text-label-secondary/80">
          {header}
        </div>
      )}
      <div className="overflow-hidden rounded-ios-lg bg-surface shadow-ios-sm divide-y divide-separator/40">
        {children}
      </div>
      {footer && (
        <div className="px-4 pt-2 text-footnote text-label-tertiary/80">
          {footer}
        </div>
      )}
    </div>
  );
}
