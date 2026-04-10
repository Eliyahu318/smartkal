import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  GitMerge,
  Sparkles,
  Sun,
  Moon,
  Smartphone,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useTheme } from "@/hooks/useTheme";
import api, { getErrorMessageHe } from "@/api/client";
import { showToast } from "@/components/Toast";
import { GroupedList } from "@/components/ui/GroupedList";
import { GroupedListRow } from "@/components/ui/GroupedListRow";
import { PageHeader } from "@/components/ui/PageHeader";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type { ThemePreference } from "@/store/themeStore";
import type { AutoMergeResponse } from "@/types/duplicates";

const THEME_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "light", label: "אור" },
  { value: "dark", label: "כהה" },
  { value: "system", label: "מערכת" },
];

const THEME_ICONS: Record<ThemePreference, typeof Sun> = {
  light: Sun,
  dark: Moon,
  system: Smartphone,
};

export function SettingsPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const { theme, setTheme } = useTheme();
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
        showToast(
          `${merged_count} פריטים אוחדו ב-${group_count} קבוצות`,
          "success",
        );
      } else {
        showToast("לא נמצאו קבוצות בטוחות לאיחוד אוטומטי", "info");
      }
    } catch (err) {
      showToast(getErrorMessageHe(err));
    } finally {
      setAutoMerging(false);
    }
  };

  const ThemeIcon = THEME_ICONS[theme];

  return (
    <div className="px-3 pb-8">
      <PageHeader
        title="הגדרות"
        subtitle="ניהול חשבון והעדפות"
        onBack={() => navigate("/more")}
      />

      {/* Account section */}
      <GroupedList header="חשבון">
        <div className="flex items-center gap-3 bg-surface px-4 py-3.5">
          {user?.picture_url ? (
            <img
              src={user.picture_url}
              alt={user.name ?? "user"}
              className="h-10 w-10 rounded-full"
            />
          ) : (
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand/15 text-headline text-brand">
              {(user?.name ?? "?")[0]?.toUpperCase()}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="text-headline text-label">{user?.name ?? "משתמש"}</p>
            <p className="mt-0.5 truncate text-subhead text-label-secondary/80">
              {user?.email ?? ""}
            </p>
          </div>
        </div>
      </GroupedList>

      {/* Appearance section — NEW */}
      <GroupedList
        header="מראה"
        footer="בחר את הערכה הצבעונית של האפליקציה. במצב 'מערכת' המראה יתאים את עצמו אוטומטית להגדרות המכשיר."
      >
        <div className="flex items-center gap-3 bg-surface px-4 py-3.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-ios-sm bg-fill/15">
            <ThemeIcon className="h-4 w-4 text-label-secondary" />
          </div>
          <div className="flex-1">
            <p className="text-body text-label">ערכת נושא</p>
          </div>
        </div>
        <div className="bg-surface px-4 pb-3.5 pt-1">
          <SegmentedControl<ThemePreference>
            options={THEME_OPTIONS}
            value={theme}
            onChange={setTheme}
            ariaLabel="ערכת נושא"
          />
        </div>
      </GroupedList>

      {/* Duplicate management section */}
      <GroupedList header="ניהול כפילויות">
        <GroupedListRow
          icon={<GitMerge className="h-4 w-4 text-label-secondary" />}
          iconBg="bg-fill/15"
          label="בדוק כפילויות"
          helperText="הצג קבוצות של פריטים דומים ואחד אותם ידנית"
          showChevron
          onClick={() => navigate("/duplicates")}
        />
        <GroupedListRow
          icon={<Sparkles className="h-4 w-4 text-accent-purple" />}
          iconBg="bg-accent-purple/15"
          label={autoMerging ? "מאחד..." : "איחוד אוטומטי של כפילויות בטוחות"}
          helperText="מאחד רק קבוצות עם דמיון גבוה — בלי לערב פריטים שונים"
          onClick={handleAutoMerge}
          disabled={autoMerging}
        />
      </GroupedList>

      {/* App info section */}
      <GroupedList header="אודות">
        <GroupedListRow
          label="גרסה"
          trailing={
            <span className="text-subhead text-label-tertiary/80">1.0.0</span>
          }
        />
      </GroupedList>
    </div>
  );
}
