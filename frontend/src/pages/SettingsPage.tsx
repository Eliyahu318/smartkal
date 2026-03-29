import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { useAuthStore } from "@/store/authStore";

export function SettingsPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  return (
    <div className="px-5 pt-14 pb-8">
      {/* Header with back button */}
      <button
        onClick={() => navigate("/more")}
        className="mb-4 flex items-center gap-1 text-sm text-green-600"
      >
        <ChevronRight className="h-4 w-4" />
        <span>חזרה</span>
      </button>

      <h1 className="text-2xl font-bold">הגדרות</h1>
      <p className="mt-1 mb-6 text-sm text-gray-500">ניהול חשבון והעדפות</p>

      {/* Account section */}
      <div className="mb-6">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
          חשבון
        </h2>
        <div className="overflow-hidden rounded-xl bg-white shadow-sm">
          <div className="px-4 py-3.5">
            <p className="text-[15px] font-medium text-gray-800">
              {user?.name ?? "משתמש"}
            </p>
            <p className="mt-0.5 text-sm text-gray-500">
              {user?.email ?? ""}
            </p>
          </div>
        </div>
      </div>

      {/* App info section */}
      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
          אודות
        </h2>
        <div className="overflow-hidden rounded-xl bg-white shadow-sm">
          <div className="flex items-center justify-between px-4 py-3.5">
            <span className="text-[15px] text-gray-800">גרסה</span>
            <span className="text-sm text-gray-400">1.0.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}
