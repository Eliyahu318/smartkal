import { type ReactNode, useEffect, useRef, useState } from "react";
import { ArrowRight } from "lucide-react";
import { motion } from "motion/react";
import { springSnappy, tapScale } from "@/lib/motion";

interface PageHeaderProps {
  /** Page title */
  title: string;
  /** Optional subtitle below the large title */
  subtitle?: string;
  /** Shows a back button (RTL: ArrowRight) and calls onBack */
  onBack?: () => void;
  /** Custom leading slot — overrides the back button */
  leading?: ReactNode;
  /** Trailing slot — action buttons shown in the compact bar */
  trailing?: ReactNode;
  /** Content rendered between the compact bar and the large title (e.g. search bar) */
  belowBar?: ReactNode;
  /** Skip the large title — only show the compact nav bar (for sub-pages) */
  compact?: boolean;
  /** Test id for E2E */
  "data-testid"?: string;
}

/**
 * iOS-style page header with collapsing large title.
 *
 * Structure:
 *   ┌─────────────────────────────┐  ← sticky, backdrop-blur
 *   │ safe-area-inset-top         │
 *   │  [back]   compact title  [+]│  ← 44px nav bar
 *   │─────────────────────────────│  ← hairline separator (when scrolled)
 *   └─────────────────────────────┘
 *   ┌─────────────────────────────┐  ← scrolls with content
 *   │  Large Title                │
 *   │  subtitle                   │
 *   └─────────────────────────────┘
 *
 * The compact title fades in when the large title scrolls out of view.
 */
export function PageHeader({
  title,
  subtitle,
  onBack,
  leading,
  trailing,
  belowBar,
  compact = false,
  "data-testid": testId,
}: PageHeaderProps) {
  const [showCompactTitle, setShowCompactTitle] = useState(compact);
  const [hasScrolled, setHasScrolled] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (compact) return; // Always show compact title in compact mode

    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    // Find the scroll container — <main> in AppShell
    const scrollRoot = sentinel.closest("main");
    if (!scrollRoot) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry) {
          setShowCompactTitle(!entry.isIntersecting);
        }
      },
      {
        root: scrollRoot,
        // Negative top margin = height of the sticky bar (safe area + 44px nav bar).
        // We approximate safe-area as 0 here — the observer fires when the sentinel
        // goes behind the sticky bar, which is "top of scroll container" visually.
        rootMargin: "-60px 0px 0px 0px",
        threshold: 0,
      },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [compact]);

  // Track whether user has scrolled at all (for separator visibility)
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const scrollRoot = sentinel.closest("main");
    if (!scrollRoot) return;

    function onScroll() {
      setHasScrolled(scrollRoot!.scrollTop > 0);
    }

    scrollRoot.addEventListener("scroll", onScroll, { passive: true });
    return () => scrollRoot.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      {/* Sticky compact nav bar */}
      <div
        data-testid={testId}
        className="sticky top-0 z-30 bg-surface/80 backdrop-blur-xl backdrop-saturate-150"
      >
        {/* Safe area spacer */}
        <div className="pt-safe" />

        {/* 44px nav bar */}
        <div className="flex h-11 items-center gap-2 px-4">
          {/* Leading: custom > back button > spacer */}
          {leading ? (
            <div className="shrink-0">{leading}</div>
          ) : onBack ? (
            <motion.button
              type="button"
              onClick={onBack}
              whileTap={tapScale}
              transition={springSnappy}
              aria-label="חזרה"
              className="-mr-1 rounded-ios-sm p-1.5 text-brand transition-colors active:text-brand-pressed"
            >
              <ArrowRight className="h-5 w-5" />
            </motion.button>
          ) : (
            <div className="w-8" />
          )}

          {/* Compact title — fades in when large title scrolls out */}
          <div className="min-w-0 flex-1">
            <span
              className={`block truncate text-center text-headline text-label transition-opacity duration-200 ${
                showCompactTitle ? "opacity-100" : "opacity-0"
              }`}
            >
              {title}
            </span>
          </div>

          {/* Trailing actions */}
          {trailing ? (
            <div className="flex shrink-0 items-center gap-1">{trailing}</div>
          ) : (
            <div className="w-8" />
          )}
        </div>

        {/* Hairline separator — visible when scrolled */}
        <div
          className={`h-px bg-separator/20 transition-opacity duration-200 ${
            hasScrolled ? "opacity-100" : "opacity-0"
          }`}
        />
      </div>

      {/* Content below the bar but above the large title (e.g. search, add input) */}
      {belowBar}

      {/* Large title area — scrolls with content */}
      {!compact && (
        <div ref={sentinelRef} className="px-5 pb-2 pt-1">
          <h1 className="text-largeTitle font-bold text-label">{title}</h1>
          {subtitle && (
            <p className="mt-0.5 text-subhead text-label-secondary/80">
              {subtitle}
            </p>
          )}
        </div>
      )}
    </>
  );
}
