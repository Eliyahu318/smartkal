import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { BottomNav } from "./BottomNav";
import { pageTransition, pageVariants } from "@/lib/motion";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const isOnboarding = location.pathname === "/" || location.pathname === "/onboarding";

  return (
    <div className="flex min-h-[100svh] items-start justify-center bg-app sm:py-8">
      {/*
        Phone frame: 430px max on desktop, full-screen on mobile.
        h-[100svh] (smallest viewport height) is intentional — it guarantees
        the frame fits within the visible area regardless of iOS Safari URL
        bar state, which lets BottomNav sit as a natural flex child below.
        Do NOT change to h-screen or h-[100dvh] — both regressed before.
      */}
      <div className="relative flex h-[100svh] w-full flex-col overflow-hidden bg-surface shadow-ios-sheet sm:h-[85vh] sm:max-w-phone sm:rounded-ios-sheet sm:ring-1 sm:ring-separator/40">
        {/* Scrollable content area */}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={pageTransition}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
        {/* Bottom nav sits naturally at bottom of the flex column — hidden during onboarding */}
        {!isOnboarding && <BottomNav />}
      </div>
    </div>
  );
}
