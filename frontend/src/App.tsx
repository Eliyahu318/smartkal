import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { ToastContainer } from "@/components/Toast";
import { ListPage } from "@/pages/ListPage";
import { ReceiptsPage } from "@/pages/ReceiptsPage";
import { MorePage } from "@/pages/MorePage";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { useAuthStore } from "@/store/authStore";

function AuthenticatedRoutes() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/list" replace />} />
        <Route path="/list" element={<ListPage />} />
        <Route path="/receipts" element={<ReceiptsPage />} />
        <Route path="/more" element={<MorePage />} />
        <Route path="*" element={<Navigate to="/list" replace />} />
      </Routes>
    </AppShell>
  );
}

function UnauthenticatedRoutes() {
  return (
    <AppShell>
      <Routes>
        <Route path="*" element={<OnboardingPage />} />
      </Routes>
    </AppShell>
  );
}

export function App() {
  const user = useAuthStore((s) => s.user);
  const initializing = useAuthStore((s) => s.initializing);
  const initialize = useAuthStore((s) => s.initialize);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-green-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <>
      <ToastContainer />
      {user ? <AuthenticatedRoutes /> : <UnauthenticatedRoutes />}
    </>
  );
}
