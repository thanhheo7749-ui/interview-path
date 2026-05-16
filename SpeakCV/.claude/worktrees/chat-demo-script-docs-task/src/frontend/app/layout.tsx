/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import "@/components/css/globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { SubscriptionProvider } from "@/context/SubscriptionContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { Toaster } from "react-hot-toast";
import type { Metadata } from "next";
import { Be_Vietnam_Pro } from "next/font/google";

import { GoogleOAuthProvider } from "@react-oauth/google";

const beVietnamPro = Be_Vietnam_Pro({
  subsets: ["vietnamese", "latin"],
  weight: ["400", "500", "600", "700", "800", "900"],
  display: "swap",
  variable: "--font-be-vietnam-pro",
});

export const metadata: Metadata = {
  title: "SpeakCV – AI Interview Practice & Professional CV Builder",
  description:
    "Practice realistic interviews with AI, get instant detailed scoring, and auto-generate professional CVs. The leading AI interview platform.",
  keywords: [
    "AI interview",
    "interview practice",
    "CV builder",
    "SpeakCV",
    "AI interview",
    "CV builder",
    "mock interview",
    "interview scoring",
  ],
  authors: [{ name: "SpeakCV Team" }],
  openGraph: {
    title: "SpeakCV – AI Interview Practice & Professional CV Builder",
    description:
      "Practice realistic interviews with AI, get instant detailed scoring, and auto-generate professional CVs.",
    type: "website",
    locale: "en_US",
    siteName: "SpeakCV",
  },
  twitter: {
    card: "summary_large_image",
    title: "SpeakCV – AI Interview Practice & Professional CV Builder",
    description:
      "Practice realistic interviews with AI, get instant detailed scoring, and auto-generate professional CVs.",
  },
  icons: {
    icon: [
      { url: "/favicon/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon/favicon-96x96.png", sizes: "96x96", type: "image/png" },
      { url: "/favicon/android-icon-192x192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [
      { url: "/favicon/apple-icon-57x57.png", sizes: "57x57" },
      { url: "/favicon/apple-icon-60x60.png", sizes: "60x60" },
      { url: "/favicon/apple-icon-72x72.png", sizes: "72x72" },
      { url: "/favicon/apple-icon-76x76.png", sizes: "76x76" },
      { url: "/favicon/apple-icon-114x114.png", sizes: "114x114" },
      { url: "/favicon/apple-icon-120x120.png", sizes: "120x120" },
      { url: "/favicon/apple-icon-144x144.png", sizes: "144x144" },
      { url: "/favicon/apple-icon-152x152.png", sizes: "152x152" },
      { url: "/favicon/apple-icon-180x180.png", sizes: "180x180" },
    ],
    other: [
      { rel: "icon", url: "/favicon/android-icon-36x36.png", sizes: "36x36", type: "image/png" },
      { rel: "icon", url: "/favicon/android-icon-48x48.png", sizes: "48x48", type: "image/png" },
      { rel: "icon", url: "/favicon/android-icon-72x72.png", sizes: "72x72", type: "image/png" },
      { rel: "icon", url: "/favicon/android-icon-96x96.png", sizes: "96x96", type: "image/png" },
      { rel: "icon", url: "/favicon/android-icon-144x144.png", sizes: "144x144", type: "image/png" },
    ],
  },
  manifest: "/favicon/manifest.json",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={beVietnamPro.className}>
        <GoogleOAuthProvider
          clientId={
            process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "YOUR_GOOGLE_CLIENT_ID"
          }
        >
        <AuthProvider>
            <SubscriptionProvider>
              <ThemeProvider>
                <Toaster position="top-right" />
                {children}
              </ThemeProvider>
            </SubscriptionProvider>
          </AuthProvider>
        </GoogleOAuthProvider>
      </body>
    </html>
  );
}
