import { forwardRef } from "react";
import type { ReactNode } from "react";
import { motion } from "motion/react";
import type { HTMLMotionProps } from "motion/react";
import { springSnappy, tapScale } from "@/lib/motion";

type IOSButtonVariant =
  | "filled"      // Brand-filled, used for primary actions
  | "tinted"      // Brand-tinted background + brand text, used for secondary actions
  | "plain"       // Text-only, used for tertiary/cancel
  | "destructive" // Danger-filled, used for delete confirmations
  | "destructive-tinted"; // Danger-tinted, used for inline delete actions

type IOSButtonSize = "sm" | "md" | "lg";

interface IOSButtonProps
  extends Omit<HTMLMotionProps<"button">, "children"> {
  variant?: IOSButtonVariant;
  size?: IOSButtonSize;
  fullWidth?: boolean;
  children: ReactNode;
}

const VARIANT_CLASSES: Record<IOSButtonVariant, string> = {
  filled:
    "bg-brand text-on-brand hover:bg-brand-hover active:bg-brand-pressed disabled:bg-fill/20 disabled:text-label-tertiary",
  tinted:
    "bg-brand/10 text-brand hover:bg-brand/15 active:bg-brand/20 disabled:bg-fill/10 disabled:text-label-tertiary",
  plain:
    "bg-transparent text-brand hover:bg-fill/10 active:bg-fill/20 disabled:text-label-tertiary",
  destructive:
    "bg-danger text-white hover:bg-danger/90 active:bg-danger/80 disabled:bg-fill/20 disabled:text-label-tertiary",
  "destructive-tinted":
    "bg-danger/10 text-danger hover:bg-danger/15 active:bg-danger/20 disabled:bg-fill/10 disabled:text-label-tertiary",
};

const SIZE_CLASSES: Record<IOSButtonSize, string> = {
  sm: "px-3 py-1.5 text-footnote rounded-ios-sm gap-1",
  md: "px-5 py-2.5 text-callout rounded-ios gap-1.5",
  lg: "px-6 py-3.5 text-headline rounded-ios gap-2",
};

/**
 * iOS-style button primitive. Built on motion.button so every variant gets
 * consistent spring tap feedback (scale 0.97).
 */
export const IOSButton = forwardRef<HTMLButtonElement, IOSButtonProps>(
  function IOSButton(
    {
      variant = "filled",
      size = "md",
      fullWidth = false,
      className = "",
      children,
      type = "button",
      disabled,
      ...props
    },
    ref,
  ) {
    return (
      <motion.button
        ref={ref}
        type={type}
        disabled={disabled}
        whileTap={disabled ? undefined : tapScale}
        transition={springSnappy}
        className={[
          "inline-flex items-center justify-center font-semibold transition-colors disabled:cursor-not-allowed",
          VARIANT_CLASSES[variant],
          SIZE_CLASSES[size],
          fullWidth ? "w-full" : "",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
        {...props}
      >
        {children}
      </motion.button>
    );
  },
);
