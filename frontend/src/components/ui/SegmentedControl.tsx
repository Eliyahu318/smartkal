import { useId } from "react";
import { motion } from "motion/react";
import { springGentle } from "@/lib/motion";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentedControlProps<T extends string> {
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  /** Optional aria-label for the entire control */
  ariaLabel?: string;
  className?: string;
}

/**
 * iOS-style segmented control. Animated thumb slides between options via
 * motion's layoutId, giving the smooth Apple-app feel without manual transforms.
 */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  className = "",
}: SegmentedControlProps<T>) {
  // Unique layoutId per control instance — multiple SegmentedControls on the
  // same page must not share a thumb element.
  const layoutId = useId();

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={`relative flex rounded-ios-sm bg-fill/15 p-0.5 ${className}`}
    >
      {options.map((option) => {
        const isActive = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => onChange(option.value)}
            className="relative flex-1 rounded-ios-sm px-3 py-1.5 text-footnote font-semibold transition-colors"
          >
            {isActive && (
              <motion.div
                layoutId={`segmented-thumb-${layoutId}`}
                transition={springGentle}
                className="absolute inset-0 rounded-ios-sm bg-surface shadow-ios-sm"
              />
            )}
            <span
              className={`relative z-10 ${
                isActive ? "text-label" : "text-label-secondary/80"
              }`}
            >
              {option.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
