/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";
import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { LEGACY_B2C } from "@/lib/features";
import { getMyProfile, upgradeToPro as upgradeApi } from "@/services/api";

interface SubscriptionContextType {
  plan: "free" | "pro";
  tokens: number;
  upgradeToPro: () => void;
  refreshSubscription: () => void;
}

const SubscriptionContext = createContext<SubscriptionContextType>(
  {} as SubscriptionContextType,
);

export const SubscriptionProvider = ({ children }: { children: ReactNode }) => {
  const [plan, setPlan] = useState<"free" | "pro">("free");
  const [tokens, setTokens] = useState(LEGACY_B2C ? 50 : 0);

  const refreshSubscription = useCallback(async () => {
    // Legacy B2C billing is off: stay neutral and make no network calls.
    if (!LEGACY_B2C) return;
    const token = sessionStorage.getItem("token");
    if (!token) {
      // Not logged in — reset to free defaults
      setPlan("free");
      setTokens(50);
      return;
    }

    try {
      const profile = await getMyProfile();
      const userPlan = profile.plan === "pro" ? "pro" : "free";
      setPlan(userPlan);
      setTokens(profile.credits ?? (userPlan === "pro" ? 10000 : 50));
    } catch {
      setPlan("free");
      setTokens(50);
    }
  }, []);

  // Refresh subscription on mount and when auth changes
  useEffect(() => {
    if (!LEGACY_B2C) return;
    refreshSubscription();

    // Listen for login/logout events
    const handleStorage = (e: StorageEvent) => {
      if (e.key === "token") {
        refreshSubscription();
      }
    };
    // auth-changed fires in the same tab (StorageEvent only fires in other tabs)
    const handleAuthChanged = () => refreshSubscription();
    window.addEventListener("auth-changed", handleAuthChanged);
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener("auth-changed", handleAuthChanged);
      window.removeEventListener("storage", handleStorage);
    };
  }, [refreshSubscription]);

  const upgradeToPro = async () => {
    if (!LEGACY_B2C) return;
    try {
      await upgradeApi();
      setPlan("pro");
      setTokens(10000);
    } catch (e) {
      console.error("Failed to upgrade:", e);
    }
  };

  return (
    <SubscriptionContext.Provider
      value={{ plan, tokens, upgradeToPro, refreshSubscription }}
    >
      {children}
    </SubscriptionContext.Provider>
  );
};

export const useSubscription = () => useContext(SubscriptionContext);
