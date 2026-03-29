import { useEffect, useRef, useCallback } from "react";
import { ShoppingCart } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { showToast } from "@/components/Toast";
import { getErrorMessageHe } from "@/api/client";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select?: boolean;
            ux_mode?: string;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              theme?: string;
              size?: string;
              text?: string;
              shape?: string;
              width?: number;
              locale?: string;
            },
          ) => void;
        };
      };
    };
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as
  | string
  | undefined;

export function OnboardingPage() {
  const loginWithGoogle = useAuthStore((s) => s.loginWithGoogle);
  const buttonRef = useRef<HTMLDivElement>(null);

  const handleCredentialResponse = useCallback(
    async (response: { credential: string }) => {
      try {
        await loginWithGoogle(response.credential);
      } catch (err: unknown) {
        showToast(getErrorMessageHe(err));
      }
    },
    [loginWithGoogle],
  );

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) {
      console.warn("VITE_GOOGLE_CLIENT_ID is not set");
      return;
    }

    const initGoogle = () => {
      if (!window.google || !buttonRef.current) return;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleCredentialResponse,
        ux_mode: "popup",
      });
      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: "outline",
        size: "large",
        text: "signin_with",
        shape: "pill",
        width: 300,
        locale: "he",
      });
    };

    // GIS script may already be loaded
    if (window.google) {
      initGoogle();
    } else {
      // Wait for script to load
      const interval = setInterval(() => {
        if (window.google) {
          clearInterval(interval);
          initGoogle();
        }
      }, 100);
      return () => clearInterval(interval);
    }
  }, [handleCredentialResponse]);

  return (
    <div className="flex h-full flex-col items-center justify-center px-6">
      {/* Logo & branding */}
      <div className="mb-8 flex flex-col items-center gap-4">
        <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-green-500 shadow-lg">
          <ShoppingCart size={40} className="text-white" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900">סמארט-כל</h1>
        <p className="text-center text-base text-gray-500">
          רשימת הקניות שמכירה אותך
        </p>
      </div>

      {/* Google Sign-In */}
      <div className="flex flex-col items-center gap-4">
        <div ref={buttonRef} />

        {!GOOGLE_CLIENT_ID && (
          <p className="text-sm text-red-500">
            Google Client ID לא הוגדר — הוסף VITE_GOOGLE_CLIENT_ID ל-.env
          </p>
        )}
      </div>

      {/* Footer */}
      <p className="mt-auto pb-8 text-center text-xs text-gray-400">
        בהתחברות אתה מסכים לתנאי השימוש ומדיניות הפרטיות
      </p>
    </div>
  );
}
