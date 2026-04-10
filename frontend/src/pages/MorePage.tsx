import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  FolderOpen,
  Settings,
  HelpCircle,
  LogOut,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { GroupedList } from "@/components/ui/GroupedList";
import { GroupedListRow } from "@/components/ui/GroupedListRow";
import { PageHeader } from "@/components/ui/PageHeader";

export function MorePage() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="px-3 pb-8">
      <PageHeader
        title="עוד"
        subtitle="הגדרות, דשבורד, וניהול קטגוריות"
      />

      <GroupedList>
        <GroupedListRow
          icon={<BarChart3 className="h-4 w-4 text-brand" />}
          iconBg="bg-brand/15"
          label="דשבורד הוצאות"
          showChevron
          onClick={() => navigate("/dashboard")}
        />
        <GroupedListRow
          icon={<FolderOpen className="h-4 w-4 text-accent-blue" />}
          iconBg="bg-accent-blue/15"
          label="ניהול קטגוריות"
          showChevron
          onClick={() => navigate("/categories")}
        />
      </GroupedList>

      <GroupedList>
        <GroupedListRow
          icon={<Settings className="h-4 w-4 text-label-secondary" />}
          iconBg="bg-fill/15"
          label="הגדרות"
          showChevron
          onClick={() => navigate("/settings")}
        />
        <GroupedListRow
          icon={<HelpCircle className="h-4 w-4 text-accent-purple" />}
          iconBg="bg-accent-purple/15"
          label="עזרה ומשוב"
          showChevron
          onClick={() =>
            window.open("mailto:support@smartkal.app", "_blank")
          }
        />
      </GroupedList>

      <GroupedList>
        <GroupedListRow
          icon={<LogOut className="h-4 w-4 text-danger" />}
          iconBg="bg-danger/15"
          label="התנתק"
          destructive
          onClick={handleLogout}
        />
      </GroupedList>
    </div>
  );
}
