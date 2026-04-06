import { useEffect, useRef, useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ShoppingCart,
  RefreshCw,
  Receipt,
  Brain,
  Upload,
  ListPlus,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
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

// ---------- Value cards for Step 2 ----------
const VALUE_CARDS = [
  {
    icon: RefreshCw,
    title: "רשימה שמרעננת את עצמה",
    description: "הרשימה לומדת את הרגלי הקנייה שלך ומחזירה מוצרים אוטומטית כשהם עומדים להיגמר",
    color: "bg-green-500",
  },
  {
    icon: Receipt,
    title: "העלה קבלה — תראה איפה זול",
    description: "צלם קבלה מהסופר ותגלה כמה היית יכול לחסוך בחנויות אחרות",
    color: "bg-blue-500",
  },
  {
    icon: Brain,
    title: "ככל שתשתמש — ככה חכמה יותר",
    description: "האפליקציה לומדת את ההעדפות שלך ומשתפרת עם כל קנייה",
    color: "bg-purple-500",
  },
] as const;

// ---------- Step 1: Login ----------
function StepLogin() {
  const loginWithGoogle = useAuthStore((s) => s.loginWithGoogle);
  const loginAsGuest = useAuthStore((s) => s.loginAsGuest);
  const [guestLoading, setGuestLoading] = useState(false);
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
        width: 320,
        locale: "he",
      });
    };

    if (window.google) {
      initGoogle();
    } else {
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
    <div className="flex h-full flex-col items-center px-6 pt-safe">
      {/* Top spacer — pushes content down from status bar */}
      <div className="flex-[2]" />

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

      {/* Google Sign-In + Guest */}
      <div className="flex w-full max-w-xs flex-col items-center gap-4">
        <div ref={buttonRef} className="flex w-full justify-center" />

        {!GOOGLE_CLIENT_ID && (
          <p className="text-sm text-red-500">
            Google Client ID לא הוגדר — הוסף VITE_GOOGLE_CLIENT_ID ל-.env
          </p>
        )}

        {/* Divider */}
        <div className="relative w-full">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-white px-2 text-gray-500">או</span>
          </div>
        </div>

        {/* Guest login */}
        <button
          onClick={async () => {
            setGuestLoading(true);
            try {
              await loginAsGuest();
            } catch (err: unknown) {
              showToast(getErrorMessageHe(err));
            } finally {
              setGuestLoading(false);
            }
          }}
          disabled={guestLoading}
          className="w-full rounded-full border-2 border-gray-300 bg-white px-8 py-3 text-base font-semibold text-gray-700 shadow-sm transition-all hover:border-green-400 hover:shadow-md disabled:opacity-50"
        >
          {guestLoading ? "מתחבר..." : "כניסה כאורח"}
        </button>
      </div>

      {/* Bottom spacer + footer */}
      <div className="flex-[3]" />
      <p className="pb-6 pb-safe text-center text-xs text-gray-400">
        בהתחברות אתה מסכים לתנאי השימוש ומדיניות הפרטיות
      </p>
    </div>
  );
}

// ---------- Step 2: Value Cards ----------
function StepValueCards({ onNext }: { onNext: () => void }) {
  const [activeCard, setActiveCard] = useState(0);
  const touchStartX = useRef(0);
  const touchEndX = useRef(0);

  const goToCard = (index: number) => {
    if (index >= 0 && index < VALUE_CARDS.length) {
      setActiveCard(index);
    }
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    const touch = e.touches[0];
    if (touch) touchStartX.current = touch.clientX;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    const touch = e.changedTouches[0];
    if (!touch) return;
    touchEndX.current = touch.clientX;
    const diff = touchStartX.current - touchEndX.current;
    // RTL: swipe left (positive diff) = next card, swipe right = previous
    if (Math.abs(diff) > 50) {
      if (diff > 0) {
        goToCard(activeCard + 1);
      } else {
        goToCard(activeCard - 1);
      }
    }
  };

  const card = VALUE_CARDS[activeCard] ?? VALUE_CARDS[0];
  const Icon = card.icon;
  const isLast = activeCard === VALUE_CARDS.length - 1;

  return (
    <div className="flex h-full flex-col items-center justify-center px-6">
      {/* Card area */}
      <div
        className="flex w-full max-w-sm flex-col items-center"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {/* Icon */}
        <div
          className={`mb-6 flex h-20 w-20 items-center justify-center rounded-full ${card.color} shadow-lg transition-all duration-300`}
        >
          <Icon size={36} className="text-white" />
        </div>

        {/* Title */}
        <h2 className="mb-3 text-center text-2xl font-bold text-gray-900 transition-all duration-300">
          {card.title}
        </h2>

        {/* Description */}
        <p className="mb-8 text-center text-base leading-relaxed text-gray-500 transition-all duration-300">
          {card.description}
        </p>

        {/* Dot indicators */}
        <div className="mb-8 flex gap-2">
          {VALUE_CARDS.map((_, i) => (
            <button
              key={i}
              onClick={() => goToCard(i)}
              className={`h-2 rounded-full transition-all duration-300 ${
                i === activeCard
                  ? "w-6 bg-green-500"
                  : "w-2 bg-gray-300"
              }`}
              aria-label={`כרטיס ${i + 1}`}
            />
          ))}
        </div>

        {/* Navigation arrows and continue button */}
        <div className="flex w-full items-center justify-between">
          <button
            onClick={() => goToCard(activeCard - 1)}
            className={`rounded-full p-2 transition-opacity ${
              activeCard === 0 ? "opacity-0" : "text-gray-400 hover:text-gray-600"
            }`}
            disabled={activeCard === 0}
            aria-label="הקודם"
          >
            <ChevronRight size={24} />
          </button>

          {isLast ? (
            <button
              onClick={onNext}
              className="rounded-full bg-green-500 px-8 py-3 text-base font-semibold text-white shadow-md transition-colors hover:bg-green-600"
            >
              המשך
            </button>
          ) : (
            <button
              onClick={() => goToCard(activeCard + 1)}
              className="rounded-full p-2 text-gray-400 transition-colors hover:text-gray-600"
              aria-label="הבא"
            >
              <ChevronLeft size={24} />
            </button>
          )}
        </div>
      </div>

      {/* Skip link */}
      <button
        onClick={onNext}
        className="mt-auto pb-8 text-sm text-gray-400 transition-colors hover:text-gray-600"
      >
        דלג
      </button>
    </div>
  );
}

// ---------- Step 3: Choose Action ----------
function StepChooseAction({
  onChoose,
}: {
  onChoose: (destination: "/receipts" | "/list") => void;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6">
      {/* Title */}
      <div className="mb-8 flex flex-col items-center gap-2">
        <h2 className="text-2xl font-bold text-gray-900">מה תרצה לעשות?</h2>
        <p className="text-center text-sm text-gray-500">
          תמיד אפשר לעשות את השני אחר כך
        </p>
      </div>

      {/* Action cards */}
      <div className="flex w-full max-w-sm flex-col gap-4">
        {/* Upload receipt card */}
        <button
          onClick={() => onChoose("/receipts")}
          className="group flex items-center gap-4 rounded-2xl border-2 border-gray-200 bg-white p-6 text-start shadow-sm transition-all hover:border-green-400 hover:shadow-md"
        >
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-green-100 transition-colors group-hover:bg-green-200">
            <Upload size={28} className="text-green-600" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">העלאת קבלה</h3>
            <p className="text-sm text-gray-500">
              צלם קבלה ונראה לך איפה אפשר לחסוך
            </p>
          </div>
        </button>

        {/* Create list card */}
        <button
          onClick={() => onChoose("/list")}
          className="group flex items-center gap-4 rounded-2xl border-2 border-gray-200 bg-white p-6 text-start shadow-sm transition-all hover:border-blue-400 hover:shadow-md"
        >
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-blue-100 transition-colors group-hover:bg-blue-200">
            <ListPlus size={28} className="text-blue-600" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">יצירת רשימה</h3>
            <p className="text-sm text-gray-500">
              התחל להוסיף מוצרים לרשימת הקניות
            </p>
          </div>
        </button>
      </div>
    </div>
  );
}

// ---------- Main Onboarding Page ----------
export function OnboardingPage() {
  const user = useAuthStore((s) => s.user);
  const onboardingComplete = useAuthStore((s) => s.onboardingComplete);
  const completeOnboarding = useAuthStore((s) => s.completeOnboarding);
  const navigate = useNavigate();

  // Determine which step to show
  // Step 1: not logged in → login
  // Step 2: logged in but not onboarded → value cards
  // Step 3: after value cards → choose action
  const [showValueCards, setShowValueCards] = useState(true);

  // If user is already onboarded (returning user who just re-logged in), skip
  useEffect(() => {
    if (user && onboardingComplete) {
      navigate("/list", { replace: true });
    }
  }, [user, onboardingComplete, navigate]);

  if (!user) {
    return <StepLogin />;
  }

  // User is authenticated but hasn't completed onboarding
  if (showValueCards) {
    return <StepValueCards onNext={() => setShowValueCards(false)} />;
  }

  return (
    <StepChooseAction
      onChoose={(destination) => {
        completeOnboarding();
        navigate(destination, { replace: true });
      }}
    />
  );
}
