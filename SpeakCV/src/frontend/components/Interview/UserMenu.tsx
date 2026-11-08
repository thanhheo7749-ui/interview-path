/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  User,
  Sparkles,
  LogOut,
  LogIn,
  ChevronUp,
  ChevronDown,
  CreditCard,
  ShieldCheck,
} from "lucide-react";
import { useSubscription } from "@/context/SubscriptionContext";

interface UserMenuProps {
  user: any;
  myProfileData: any;
  isAdmin: boolean;
  logout: () => void;
  onOpenSubscription?: () => void;
}

export function UserMenu({ user, myProfileData, isAdmin, logout, onOpenSubscription }: UserMenuProps) {
  const router = useRouter();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const { tokens, plan } = useSubscription();

  if (!user) {
    return (
      <button
        onClick={() => router.push("/login")}
        className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-theme-text rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-blue-500/20 active:scale-95 transition-all"
      >
        <LogIn size={18} /> Sign In / Sign Up
      </button>
    );
  }

  return (
    <div className="relative">
      <div
        onClick={() => setShowUserMenu(!showUserMenu)}
        className="flex items-center gap-3 cursor-pointer hover:bg-theme-surface p-2 rounded-xl transition-colors border border-transparent hover:border-theme-border"
      >
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center overflow-hidden shrink-0 border border-slate-600">
          {myProfileData?.info?.avatar || myProfileData?.avatar ? (
            <img
              src={myProfileData?.info?.avatar || myProfileData?.avatar}
              alt={`Avatar of ${myProfileData?.full_name || "user"}`}
              className="w-full h-full object-cover"
              onError={(e) => {
                const name = encodeURIComponent(myProfileData?.full_name || "User");
                e.currentTarget.src = `https://ui-avatars.com/api/?name=${name}&background=random`;
              }}
            />
          ) : (
            <User className="text-theme-text" size={20} />
          )}
        </div>
        <div className="flex-1 overflow-hidden">
          <p className="text-theme-text font-bold text-sm truncate">
            {myProfileData?.full_name || user}
          </p>
          <div className="flex text-[11px] items-center gap-1 mt-0.5 font-medium text-theme-text-secondary">
            <Sparkles size={10} className="text-yellow-400" />
            <span>
              Interactions: <span className="text-yellow-400 font-bold">{tokens}</span>{" "}
              {plan === "pro" && "(Pro)"}
            </span>
          </div>
        </div>
        {showUserMenu ? (
          <ChevronUp size={16} className="text-theme-text-secondary" />
        ) : (
          <ChevronDown size={16} className="text-theme-text-secondary" />
        )}
      </div>

      {showUserMenu && (
        <div className="absolute top-[105%] left-0 right-0 bg-theme-surface border border-theme-border rounded-xl shadow-2xl p-2 animate-in slide-in-from-top-2 z-50">
          <button
            onClick={() => {
              router.push("/profile");
              setShowUserMenu(false);
            }}
            className="w-full text-left px-4 py-2 text-sm text-theme-text hover:bg-theme-border hover:text-theme-accent rounded-lg flex items-center gap-3"
          >
            <User size={16} /> My Profile
          </button>
          <button
            onClick={() => {
              if (onOpenSubscription) onOpenSubscription();
              setShowUserMenu(false);
            }}
            className="w-full text-left px-4 py-2 text-sm text-theme-text hover:bg-theme-border hover:text-blue-600 rounded-lg flex items-center gap-3"
          >
            <CreditCard size={16} /> My Subscription
          </button>
          {isAdmin && (
            <button
              onClick={() => {
                router.push("/admin");
                setShowUserMenu(false);
              }}
              className="w-full text-left px-4 py-2 text-sm text-orange-400 hover:bg-theme-border rounded-lg flex items-center gap-3"
            >
              <ShieldCheck size={16} /> Admin Panel
            </button>
          )}
          <button
            onClick={() => {
              logout();
              setShowUserMenu(false);
            }}
            className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-theme-border rounded-lg flex items-center gap-3 mt-1"
          >
            <LogOut size={16} /> Log Out
          </button>
        </div>
      )}
    </div>
  );
}
