import type { ReactNode } from "react";

type BadgeVariant = "mint" | "purple" | "blue" | "gray" | "danger" | "warning";

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  mint: "bg-brand/10 text-brand border-brand/20",
  purple: "bg-accent-purple/10 text-accent-purple border-accent-purple/20",
  blue: "bg-accent-blue/10 text-accent-blue border-accent-blue/20",
  gray: "bg-fill/15 text-label-secondary border-separator/40",
  danger: "bg-danger/10 text-danger border-danger/20",
  warning: "bg-warning/10 text-warning border-warning/20",
};

/**
 * Pill component used for status indicators, count chips, and tags.
 * Color variants map to the semantic tokens (brand, categorical accents, status).
 */
export function Badge({
  variant = "mint",
  children,
  className = "",
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-caption1 font-semibold ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
