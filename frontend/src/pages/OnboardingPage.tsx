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
    color: "bg-brand",
  },
  {
    icon: Receipt,
    title: "העלה קבלה — תראה איפה זול",
    description: "צלם קבלה מהסופר ותגלה כמה היית יכול לחסוך בחנויות אחרות",
    color: "bg-accent-blue",
  },
  {
    icon: Brain,
    title: "ככל שתשתמש — ככה חכמה יותר",
    description: "האפליקציה לומדת את ההעדפות שלך ומשתפרת עם כל קנייה",
    color: "bg-accent-purple",
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
    <div
      className="relative flex h-full flex-col items-center px-6 pt-safe"
      style={{
        backgroundImage:
          "radial-gradient(ellipse 80% 60% at 50% 0%, rgb(var(--brand) / 0.12), transparent 70%)",
      }}
    >
      {/* Top spacer — pushes content down from status bar */}
      <div className="flex-[2]" />

      {/* Logo & branding */}
      <div className="mb-8 flex flex-col items-center gap-4">
        <div className="flex h-20 w-20 items-center justify-center rounded-ios-lg bg-brand shadow-ios-lg">
          <ShoppingCart size={40} className="text-on-brand" />
        </div>
        <h1 className="text-largeTitle text-label">סמארט-כל</h1>
        <p className="text-center text-body text-label-secondary/80">
          רשימת הקניות שמכירה אותך
        </p>
      </div>

      {/* Google Sign-In + Guest */}
      <div className="flex w-full max-w-xs flex-col items-center gap-4">
        {/* Frame Google's white pill so it looks intentional in dark mode */}
        <div className="rounded-full bg-surface p-1 ring-1 ring-separator/40">
          <div ref={buttonRef} className="flex justify-center" />
        </div>

        {!GOOGLE_CLIENT_ID && (
          <p className="text-subhead text-danger">
            Google Client ID לא הוגדר — הוסף VITE_GOOGLE_CLIENT_ID ל-.env
          </p>
        )}

        {/* Divider */}
        <div className="relative w-full">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-separator/60" />
          </div>
          <div className="relative flex justify-center text-caption2 uppercase">
            <span className="bg-surface px-2 text-label-tertiary/80">או</span>
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
          className="w-full rounded-full border border-separator/60 bg-surface px-8 py-3 text-callout font-semibold text-label shadow-ios-sm transition-all hover:border-brand/40 hover:bg-brand/5 active:scale-[0.98] disabled:opacity-50"
        >
          {guestLoading ? "מתחבר..." : "כניסה כאורח"}
        </button>
      </div>

      {/* Bottom spacer + footer */}
      <div className="flex-[3]" />
      <p className="pb-6 pb-safe text-center text-caption1 text-label-tertiary/70">
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
          className={`mb-6 flex h-20 w-20 items-center justify-center rounded-full ${card.color} shadow-ios-lg transition-all duration-300`}
        >
          <Icon size={36} className="text-on-brand" />
        </div>

        {/* Title */}
        <h2 className="mb-3 text-center text-title1 text-label transition-all duration-300">
          {card.title}
        </h2>

        {/* Description */}
        <p className="mb-8 text-center text-body leading-relaxed text-label-secondary/80 transition-all duration-300">
          {card.description}
        </p>

        {/* Dot indicators */}
        <div className="mb-8 flex gap-2">
          {VALUE_CARDS.map((_, i) => (
            <button
              key={i}
              onClick={() => goToCard(i)}
              className={`h-2 rounded-full transition-all duration-300 ${
                i === activeCard ? "w-6 bg-brand" : "w-2 bg-fill/30"
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
              activeCard === 0
                ? "opacity-0"
                : "text-label-tertiary hover:text-label-secondary"
            }`}
            disabled={activeCard === 0}
            aria-label="הקודם"
          >
            <ChevronRight size={24} />
          </button>

          {isLast ? (
            <button
              onClick={onNext}
              className="rounded-full bg-brand px-8 py-3 text-callout font-semibold text-on-brand shadow-ios-md transition-all hover:bg-brand-hover active:scale-[0.97]"
            >
              המשך
            </button>
          ) : (
            <button
              onClick={() => goToCard(activeCard + 1)}
              className="rounded-full p-2 text-label-tertiary transition-colors hover:text-label-secondary"
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
        className="mt-auto pb-8 text-subhead text-label-tertiary transition-colors hover:text-label-secondary"
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
        <h2 className="text-title1 text-label">מה תרצה לעשות?</h2>
        <p className="text-center text-subhead text-label-secondary/80">
          תמיד אפשר לעשות את השני אחר כך
        </p>
      </div>

      {/* Action cards */}
      <div className="flex w-full max-w-sm flex-col gap-4">
        {/* Upload receipt card */}
        <button
          onClick={() => onChoose("/receipts")}
          className="group flex items-center gap-4 rounded-ios-lg border border-separator/40 bg-surface p-6 text-start shadow-ios-sm transition-all hover:border-brand/40 hover:shadow-ios-md active:scale-[0.98]"
        >
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-ios bg-brand/15 transition-colors group-hover:bg-brand/20">
            <Upload size={28} className="text-brand" />
          </div>
          <div>
            <h3 className="text-headline text-label">העלאת קבלה</h3>
            <p className="text-subhead text-label-secondary/80">
              צלם קבלה ונראה לך איפה אפשר לחסוך
            </p>
          </div>
        </button>

        {/* Create list card */}
        <button
          onClick={() => onChoose("/list")}
          className="group flex items-center gap-4 rounded-ios-lg border border-separator/40 bg-surface p-6 text-start shadow-ios-sm transition-all hover:border-accent-blue/40 hover:shadow-ios-md active:scale-[0.98]"
        >
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-ios bg-accent-blue/15 transition-colors group-hover:bg-accent-blue/20">
            <ListPlus size={28} className="text-accent-blue" />
          </div>
          <div>
            <h3 className="text-headline text-label">יצירת רשימה</h3>
            <p className="text-subhead text-label-secondary/80">
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
