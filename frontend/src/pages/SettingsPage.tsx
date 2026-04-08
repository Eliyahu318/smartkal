import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, GitMerge, Sparkles } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import api, { getErrorMessageHe } from "@/api/client";
import { showToast } from "@/components/Toast";
import type { AutoMergeResponse } from "@/types/duplicates";

export function SettingsPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const [autoMerging, setAutoMerging] = useState(false);

  const handleAutoMerge = async () => {
    if (autoMerging) return;
    setAutoMerging(true);
    try {
      const res = await api.post<AutoMergeResponse>(
        "/api/v1/list/duplicates/auto-merge",
      );
      const { merged_count, group_count } = res.data;
      if (merged_count > 0) {
        showToast(`${merged_count} פריטים אוחדו ב-${group_count} קבוצות`, "success");
      } else {
        showToast("לא נמצאו קבוצות בטוחות לאיחוד אוטומטי", "info");
      }
    } catch (err) {
      showToast(getErrorMessageHe(err));
    } finally {
      setAutoMerging(false);
    }
  };

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

      {/* Duplicate management section */}
      <div className="mb-6">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
          ניהול כפילויות
        </h2>
        <div className="overflow-hidden rounded-xl bg-white shadow-sm">
          <button
            type="button"
            onClick={() => navigate("/duplicates")}
            className="flex w-full items-center justify-between px-4 py-3.5 text-right hover:bg-gray-50"
          >
            <div className="flex items-center gap-3">
              <GitMerge className="h-5 w-5 text-gray-500" />
              <div>
                <p className="text-[15px] font-medium text-gray-800">בדוק כפילויות</p>
                <p className="text-xs text-gray-500">
                  הצג קבוצות של פריטים דומים ואחד אותם ידנית
                </p>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 -rotate-180 text-gray-400" />
          </button>
          <div className="border-t border-gray-100" />
          <button
            type="button"
            onClick={handleAutoMerge}
            disabled={autoMerging}
            className="flex w-full items-center justify-between px-4 py-3.5 text-right hover:bg-gray-50 disabled:opacity-50"
          >
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-[15px] font-medium text-gray-800">
                  {autoMerging ? "מאחד..." : "איחוד אוטומטי של כפילויות בטוחות"}
                </p>
                <p className="text-xs text-gray-500">
                  מאחד רק קבוצות עם דמיון גבוה — בלי לערב פריטים שונים
                </p>
              </div>
            </div>
          </button>
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
