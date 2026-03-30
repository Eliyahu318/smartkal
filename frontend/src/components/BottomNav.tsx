import { useLocation, useNavigate } from "react-router-dom";
import { ClipboardList, Receipt, MoreHorizontal } from "lucide-react";

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
    <nav className="absolute inset-x-0 bottom-0 flex items-center justify-around border-t border-gray-200 bg-white/95 pb-safe backdrop-blur-sm sm:rounded-b-3xl">
      {NAV_ITEMS.map((item) => {
        const isActive = location.pathname === item.path;
        const Icon = item.icon;

        return (
          <button
            key={item.path}
            data-testid={item.testId}
            onClick={() => navigate(item.path)}
            className={`flex flex-1 flex-col items-center gap-0.5 pb-2 pt-3 text-xs transition-colors ${
              isActive
                ? "text-green-600"
                : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <Icon size={22} strokeWidth={isActive ? 2.5 : 1.5} />
            <span className={isActive ? "font-semibold" : "font-normal"}>
              {item.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
