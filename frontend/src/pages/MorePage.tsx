import { useNavigate } from "react-router-dom";
import { BarChart3, ChevronLeft } from "lucide-react";

interface MenuItemProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}

function MenuItem({ icon, label, onClick }: MenuItemProps) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-xl bg-white px-4 py-3.5 text-start shadow-sm active:bg-gray-50"
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-50 text-green-600">
        {icon}
      </span>
      <span className="flex-1 text-[15px] font-medium text-gray-800">{label}</span>
      <ChevronLeft className="h-4 w-4 text-gray-300" />
    </button>
  );
}

export function MorePage() {
  const navigate = useNavigate();

  return (
    <div className="px-5 pt-14">
      <h1 className="text-2xl font-bold">עוד</h1>
      <p className="mt-1 mb-5 text-sm text-gray-500">הגדרות, דשבורד, וניהול קטגוריות</p>

      <div className="space-y-2">
        <MenuItem
          icon={<BarChart3 className="h-5 w-5" />}
          label="דשבורד הוצאות"
          onClick={() => navigate("/dashboard")}
        />
      </div>
    </div>
  );
}
