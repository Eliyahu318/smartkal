import { create } from "zustand";
import api, { registerAuthBridge } from "@/api/client";

// ---------- Types ----------
export interface User {
  id: string;
  email: string;
  name: string;
  picture_url: string | null;
  is_active: boolean;
}

interface AuthState {
  /** Current user — null means not authenticated */
  user: User | null;
  /** True while we are verifying an existing session on app boot */
  initializing: boolean;
  /** In-memory access token (refresh token lives in httpOnly cookie) */
  _accessToken: string | null;
  /** Whether user has completed the onboarding flow */
  onboardingComplete: boolean;

  /** Log in with a Google id_token received from GIS */
  loginWithGoogle: (idToken: string) => Promise<void>;
  /** Log in as a guest (no credentials needed) */
  loginAsGuest: () => Promise<void>;
  /** Refresh the token pair; returns new access token or null */
  refreshTokens: () => Promise<string | null>;
  /** Fetch the current user profile */
  fetchMe: () => Promise<void>;
  /** Clear all auth state */
  logout: () => void;
  /** Boot sequence — try to restore session (always resolves) */
  initialize: () => Promise<void>;
  /** Mark onboarding as complete */
  completeOnboarding: () => void;
}

const ONBOARDING_KEY = "smartkal_onboarded";

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  initializing: true,
  _accessToken: null,
  onboardingComplete: localStorage.getItem(ONBOARDING_KEY) === "1",

  loginWithGoogle: async (idToken: string) => {
    const { data } = await api.post<{
      access_token: string;
      token_type: string;
    }>("/api/v1/auth/google", { id_token: idToken });

    set({ _accessToken: data.access_token });

    // Fetch user profile
    await get().fetchMe();
  },

  loginAsGuest: async () => {
    const { data } = await api.post<{
      access_token: string;
      token_type: string;
    }>("/api/v1/auth/guest", {});

    set({ _accessToken: data.access_token });

    await get().fetchMe();
  },

  refreshTokens: async () => {
    try {
      // Refresh token is sent automatically via httpOnly cookie
      const { data } = await api.post<{
        access_token: string;
        token_type: string;
      }>("/api/v1/auth/refresh");

      set({ _accessToken: data.access_token });
      return data.access_token;
    } catch {
      // Refresh failed — clear state
      get().logout();
      return null;
    }
  },

  fetchMe: async () => {
    const { data } = await api.get<User>("/api/v1/auth/me");
    set({ user: data });
  },

  logout: () => {
    // Fire-and-forget: clear the httpOnly cookie on the server
    api.post("/api/v1/auth/logout").catch(() => {});
    set({ user: null, _accessToken: null });
  },

  initialize: async () => {
    // Try to restore the session using the httpOnly refresh token cookie.
    try {
      const { data } = await api.post<{
        access_token: string;
        token_type: string;
      }>("/api/v1/auth/refresh");

      set({ _accessToken: data.access_token });
      await get().fetchMe();
    } catch {
      // No valid session — user needs to log in
    } finally {
      set({ initializing: false });
    }
  },

  completeOnboarding: () => {
    localStorage.setItem(ONBOARDING_KEY, "1");
    set({ onboardingComplete: true });
  },
}));

// ---------- Wire the auth bridge so the Axios interceptor can access tokens ----------
registerAuthBridge({
  getAccessToken: () => useAuthStore.getState()._accessToken,
  attemptTokenRefresh: () => useAuthStore.getState().refreshTokens(),
  forceLogout: () => useAuthStore.getState().logout(),
});
