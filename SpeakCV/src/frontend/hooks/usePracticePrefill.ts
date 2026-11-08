/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { useEffect, useRef, useState } from "react";
import { loadPracticeSettings } from "@/lib/practiceSettingsStorage";
import { resolvePrefill, type PracticeConfig } from "@/lib/practicePrefill";
import { getApplication, getPublicJob } from "@/services/hiring";

const APPLICATION_ID_RE = /^[1-9]\d{0,9}$/;

interface UsePracticePrefillArgs {
  config: PracticeConfig;
  setConfig: (c: any) => void;
  interviewHistories?: any[];
  applicationId?: string | null;
  isLoggedIn?: boolean;
}

/** Fills Setup fields from localStorage, the last practice row, and (if present) the candidate's application. */
export function usePracticePrefill({
  config,
  setConfig,
  interviewHistories,
  applicationId,
  isLoggedIn,
}: UsePracticePrefillArgs) {
  const localRanRef = useRef(false);
  const historyRanRef = useRef(false);
  const appRanRef = useRef(false);
  const [prefillNotice, setPrefillNotice] = useState<{ label: string } | null>(null);

  const hasAppContext = Boolean(applicationId && APPLICATION_ID_RE.test(applicationId));

  useEffect(() => {
    if (localRanRef.current) return;
    localRanRef.current = true;

    const local = loadPracticeSettings();
    if (!local) return;
    const { patch } = resolvePrefill(config, { local });
    if (Object.keys(patch).length > 0) setConfig({ ...config, ...patch });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (historyRanRef.current || !interviewHistories || interviewHistories.length === 0) return;
    historyRanRef.current = true;

    const last = interviewHistories[0];
    // An application context (phase 4) owns position/company/jd; history still supplies voice/mode.
    const history = {
      position: hasAppContext ? null : last.position,
      company: hasAppContext ? null : last.company,
      jd: hasAppContext ? null : last.jd_text,
      voice: last.voice,
      mode: last.mode,
    };
    const { patch, filledFrom } = resolvePrefill(config, { history });
    if (Object.keys(patch).length > 0) setConfig({ ...config, ...patch });
    if (filledFrom.position || filledFrom.company || filledFrom.jd) {
      setPrefillNotice({
        label: last.company ? `Filled from your last practice (${last.company})` : "Filled from your last practice",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interviewHistories, hasAppContext]);

  useEffect(() => {
    if (appRanRef.current || !hasAppContext || !isLoggedIn) return;
    appRanRef.current = true;
    let ignore = false;

    (async () => {
      try {
        const application = await getApplication(Number(applicationId));
        let jd = "";
        if (application.job_slug) {
          try {
            const job = await getPublicJob(application.job_slug);
            const requirementLines = job.requirements.map((r) => `- ${r.text}`).join("\n");
            jd = requirementLines ? `${job.description}\n\nRequirements:\n${requirementLines}` : job.description;
          } catch (error) {
            console.warn("usePracticePrefill: public job lookup failed", error);
          }
        }
        if (ignore) return;
        const { patch, filledFrom } = resolvePrefill(config, {
          app: { position: application.job_title, company: application.company_name, jd },
        });
        if (Object.keys(patch).length > 0) setConfig({ ...config, ...patch });
        if (filledFrom.position || filledFrom.company || filledFrom.jd) {
          setPrefillNotice({ label: `Filled from your application: ${application.job_title} at ${application.company_name}` });
        }
      } catch (error) {
        console.warn("usePracticePrefill: application lookup failed", error);
      }
    })();

    return () => {
      ignore = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasAppContext, applicationId, isLoggedIn]);

  const clearPrefill = () => {
    setConfig({ ...config, position: "", company: "", jd: "" });
    setPrefillNotice(null);
  };

  return { prefillNotice, clearPrefill };
}
