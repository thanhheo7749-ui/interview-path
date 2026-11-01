"use client";

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ScreeningRoom } from "@/components/Hiring/ScreeningRoom";
import { useAuth } from "@/context/AuthContext";

// In Next.js 16 `params` is a promise; a client page unwraps it with `use`.
export default function ScreeningPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { token, isLoading } = useAuth();
  const router = useRouter();
  const applicationId = Number(id);

  useEffect(() => {
    if (!isLoading && !token) {
      router.replace(`/login?redirect=${encodeURIComponent(`/applications/${id}/screening`)}`);
    }
  }, [isLoading, token, router, id]);

  if (isLoading || !token || !Number.isInteger(applicationId)) return null;
  return <ScreeningRoom applicationId={applicationId} />;
}
