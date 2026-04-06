import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { BottomNav } from "./BottomNav";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const isOnboarding = location.pathname === "/" || location.pathname === "/onboarding";

  return (
    <div className="flex min-h-[100dvh] items-start justify-center bg-gray-200 sm:py-8">
      {/* Phone frame: 430px max on desktop, full-screen on mobile */}
      <div className="relative flex h-[100dvh] w-full flex-col bg-white shadow-2xl sm:h-[85vh] sm:max-w-phone sm:rounded-3xl sm:ring-1 sm:ring-gray-200">
        {/* Scrollable content area */}
        <main className={`flex-1 overflow-y-auto ${isOnboarding ? "" : "pb-20"}`}>
          {children}
        </main>
        {/* Fixed bottom nav — hidden during onboarding */}
        {!isOnboarding && <BottomNav />}
      </div>
    </div>
  );
}
