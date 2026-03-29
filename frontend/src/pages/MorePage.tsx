import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  ChevronLeft,
  FolderOpen,
  Settings,
  HelpCircle,
  LogOut,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";

interface MenuItemProps {
  icon: React.ReactNode;
  iconBg?: string;
  label: string;
  onClick: () => void;
}

function MenuItem({
  icon,
  iconBg = "bg-green-50 text-green-600",
  label,
  onClick,
}: MenuItemProps) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-3 bg-white px-4 py-3.5 text-start active:bg-gray-50"
    >
      <span
        className={`flex h-8 w-8 items-center justify-center rounded-lg ${iconBg}`}
      >
        {icon}
      </span>
      <span className="flex-1 text-[15px] font-medium text-gray-800">
        {label}
      </span>
      <ChevronLeft className="h-4 w-4 text-gray-300" />
    </button>
  );
}

function MenuDivider() {
  return <div className="h-px bg-gray-100 ms-16" />;
}

interface MenuGroupProps {
  children: React.ReactNode;
}

function MenuGroup({ children }: MenuGroupProps) {
  return (
    <div className="overflow-hidden rounded-xl bg-white shadow-sm">
      {children}
    </div>
  );
}

export function MorePage() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="px-5 pt-14 pb-8">
      <h1 className="text-2xl font-bold">עוד</h1>
      <p className="mt-1 mb-5 text-sm text-gray-500">
        הגדרות, דשבורד, וניהול קטגוריות
      </p>

      <div className="space-y-4">
        <MenuGroup>
          <MenuItem
            icon={<BarChart3 className="h-5 w-5" />}
            label="דשבורד הוצאות"
            onClick={() => navigate("/dashboard")}
          />
          <MenuDivider />
          <MenuItem
            icon={<FolderOpen className="h-5 w-5" />}
            iconBg="bg-blue-50 text-blue-600"
            label="ניהול קטגוריות"
            onClick={() => navigate("/categories")}
          />
        </MenuGroup>

        <MenuGroup>
          <MenuItem
            icon={<Settings className="h-5 w-5" />}
            iconBg="bg-gray-100 text-gray-600"
            label="הגדרות"
            onClick={() => navigate("/settings")}
          />
          <MenuDivider />
          <MenuItem
            icon={<HelpCircle className="h-5 w-5" />}
            iconBg="bg-purple-50 text-purple-600"
            label="עזרה ומשוב"
            onClick={() =>
              window.open("mailto:support@smartkal.app", "_blank")
            }
          />
        </MenuGroup>

        <MenuGroup>
          <MenuItem
            icon={<LogOut className="h-5 w-5" />}
            iconBg="bg-red-50 text-red-500"
            label="התנתק"
            onClick={handleLogout}
          />
        </MenuGroup>
      </div>
    </div>
  );
}
