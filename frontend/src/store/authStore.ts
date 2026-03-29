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

interface TokenPair {
  access_token: string;
  refresh_token: string;
}

interface AuthState {
  /** Current user — null means not authenticated */
  user: User | null;
  /** True while we are verifying an existing session on app boot */
  initializing: boolean;
  /** In-memory tokens (never persisted to localStorage) */
  _tokens: TokenPair | null;
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
  _tokens: null,
  onboardingComplete: localStorage.getItem(ONBOARDING_KEY) === "1",

  loginWithGoogle: async (idToken: string) => {
    const { data } = await api.post<{
      access_token: string;
      refresh_token: string;
      token_type: string;
    }>("/api/v1/auth/google", { id_token: idToken });

    const tokens: TokenPair = {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
    };
    set({ _tokens: tokens });

    // Fetch user profile
    await get().fetchMe();
  },

  loginAsGuest: async () => {
    const { data } = await api.post<{
      access_token: string;
      refresh_token: string;
      token_type: string;
    }>("/api/v1/auth/guest", {});

    const tokens: TokenPair = {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
    };
    set({ _tokens: tokens });

    await get().fetchMe();
  },

  refreshTokens: async () => {
    const tokens = get()._tokens;
    if (!tokens?.refresh_token) return null;

    try {
      const { data } = await api.post<{
        access_token: string;
        refresh_token: string;
        token_type: string;
      }>("/api/v1/auth/refresh", {
        refresh_token: tokens.refresh_token,
      });

      const newTokens: TokenPair = {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      };
      set({ _tokens: newTokens });
      return newTokens.access_token;
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
    set({ user: null, _tokens: null });
  },

  initialize: async () => {
    // Tokens live only in memory — on page reload there is nothing to
    // restore, so we simply mark init as done.
    set({ initializing: false });
  },

  completeOnboarding: () => {
    localStorage.setItem(ONBOARDING_KEY, "1");
    set({ onboardingComplete: true });
  },
}));

// ---------- Wire the auth bridge so the Axios interceptor can access tokens ----------
registerAuthBridge({
  getAccessToken: () => useAuthStore.getState()._tokens?.access_token ?? null,
  attemptTokenRefresh: () => useAuthStore.getState().refreshTokens(),
  forceLogout: () => useAuthStore.getState().logout(),
});
