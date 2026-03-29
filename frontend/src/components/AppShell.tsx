import type { ReactNode } from "react";
import { BottomNav } from "./BottomNav";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex min-h-screen items-start justify-center bg-gray-200 sm:py-8">
      {/* Phone frame: 430px max on desktop, full-screen on mobile */}
      <div className="relative flex h-screen w-full flex-col bg-white shadow-2xl sm:h-[85vh] sm:max-w-phone sm:rounded-3xl sm:ring-1 sm:ring-gray-200">
        {/* Scrollable content area */}
        <main className="flex-1 overflow-y-auto pb-20">
          {children}
        </main>
        {/* Fixed bottom nav */}
        <BottomNav />
      </div>
    </div>
  );
}
