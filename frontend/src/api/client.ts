import axios from "axios";

/** Error code → Hebrew user-facing message */
const ERROR_MESSAGES_HE: Record<string, string> = {
  AUTHENTICATION_ERROR: "שגיאת אימות — נא להתחבר מחדש",
  VALIDATION_ERROR: "הנתונים שהוזנו אינם תקינים",
  NOT_FOUND: "הפריט לא נמצא",
  RATE_LIMIT_ERROR: "יותר מדי בקשות — נסה שוב בעוד דקה",
  EXTERNAL_SERVICE_ERROR: "שגיאה בשירות חיצוני — נסה שוב",
  RECEIPT_PARSING_ERROR: "לא הצלחנו לקרוא את הקבלה",
  CLAUDE_API_ERROR: "שגיאה בשירות AI — נסה שוב",
  SUPERGET_ERROR: "שגיאה בשירות השוואת מחירים",
  DATABASE_ERROR: "שגיאת מערכת — נסה שוב",
};

const DEFAULT_ERROR_HE = "שגיאה לא צפויה — נסה שוב";

export interface ApiError {
  code: string;
  message: string;
  message_en: string;
  details: Record<string, unknown>;
}

/**
 * Resolve a Hebrew toast message from a backend error response.
 */
export function getErrorMessageHe(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const code = (error.response?.data as { error?: { code?: string } })?.error
      ?.code;
    if (code && code in ERROR_MESSAGES_HE) {
      return ERROR_MESSAGES_HE[code]!;
    }
  }
  return DEFAULT_ERROR_HE;
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// ---------- request interceptor: attach access token ----------
api.interceptors.request.use((config) => {
  // Lazy import to avoid circular dependency (authStore imports client)
  // We read directly from the module-level getter exposed by the store.
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---------- response interceptor: auto-refresh on 401 ----------
let refreshPromise: Promise<string | null> | null = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (!axios.isAxiosError(error) || !error.config) {
      return Promise.reject(error);
    }

    const originalRequest = error.config as typeof error.config & {
      _retry?: boolean;
    };

    // Only attempt refresh once per request, and not for auth endpoints
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/")
    ) {
      originalRequest._retry = true;

      try {
        // Coalesce concurrent refreshes into a single request
        if (!refreshPromise) {
          refreshPromise = attemptTokenRefresh();
        }
        const newToken = await refreshPromise;
        refreshPromise = null;

        if (newToken) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api(originalRequest);
        }
      } catch {
        refreshPromise = null;
      }

      // Refresh failed — force logout
      forceLogout();
    }

    return Promise.reject(error);
  },
);

// ---- Store bridge (set by authStore on init to break circular dep) ----
let getAccessToken: () => string | null = () => null;
let attemptTokenRefresh: () => Promise<string | null> = () =>
  Promise.resolve(null);
let forceLogout: () => void = () => {};

export function registerAuthBridge(bridge: {
  getAccessToken: () => string | null;
  attemptTokenRefresh: () => Promise<string | null>;
  forceLogout: () => void;
}) {
  getAccessToken = bridge.getAccessToken;
  attemptTokenRefresh = bridge.attemptTokenRefresh;
  forceLogout = bridge.forceLogout;
}

export default api;
