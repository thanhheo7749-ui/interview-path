import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { LEGACY_B2C } from "@/lib/features";

export default function Layout({ children }: { children: ReactNode }) {
  if (!LEGACY_B2C) notFound();
  return <>{children}</>;
}
