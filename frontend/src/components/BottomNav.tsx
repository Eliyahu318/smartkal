import { useLocation, useNavigate } from "react-router-dom";
import { ClipboardList, Receipt, MoreHorizontal } from "lucide-react";
import { motion } from "motion/react";
import { springGentle } from "@/lib/motion";

interface NavItem {
  path: string;
  label: string;
  icon: typeof ClipboardList;
}

const NAV_ITEMS: (NavItem & { testId: string })[] = [
  { path: "/list", label: "רשימה", icon: ClipboardList, testId: "nav-list" },
  { path: "/receipts", label: "קבלות", icon: Receipt, testId: "nav-receipts" },
  { path: "/more", label: "עוד", icon: MoreHorizontal, testId: "nav-more" },
];

export function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav className="flex flex-none items-center justify-around border-t border-separator/20 bg-surface/80 backdrop-blur-xl backdrop-saturate-150 pb-safe sm:pb-0 sm:rounded-b-ios-sheet">
      {NAV_ITEMS.map((item) => {
        const isActive = location.pathname === item.path;
        const Icon = item.icon;

        return (
          <button
            key={item.path}
            data-testid={item.testId}
            onClick={() => navigate(item.path)}
            className="relative flex flex-1 flex-col items-center gap-0.5 pb-1.5 pt-2"
          >
            {/* Animated active pill — slides between tabs via shared layoutId */}
            {isActive && (
              <motion.div
                layoutId="nav-pill"
                transition={springGentle}
                className="absolute inset-x-3 inset-y-1 rounded-ios bg-brand/10"
              />
            )}
            {/* Icon + label sit above the pill via z-index */}
            <Icon
              size={24}
              strokeWidth={isActive ? 2.2 : 1.6}
              className={`relative z-10 transition-colors ${
                isActive ? "text-brand" : "text-label-tertiary/60"
              }`}
            />
            <span
              className={`relative z-10 text-caption2 transition-colors ${
                isActive ? "font-semibold text-brand" : "text-label-tertiary/60"
              }`}
            >
              {item.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
