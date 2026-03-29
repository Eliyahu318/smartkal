import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { ListPage } from "@/pages/ListPage";
import { ReceiptsPage } from "@/pages/ReceiptsPage";
import { MorePage } from "@/pages/MorePage";

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/list" replace />} />
        <Route path="/list" element={<ListPage />} />
        <Route path="/receipts" element={<ReceiptsPage />} />
        <Route path="/more" element={<MorePage />} />
      </Routes>
    </AppShell>
  );
}
