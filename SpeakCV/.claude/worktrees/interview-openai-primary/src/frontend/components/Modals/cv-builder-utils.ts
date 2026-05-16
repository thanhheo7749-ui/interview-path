/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 *
 * Shared utilities for the CV Builder (GenCVModal).
 * Extracted to reduce duplication and keep the main component lean.
 */

// ──────────────────────────────────────────────
// Constants — Smart Hints for CV sections
// ──────────────────────────────────────────────

export const HINTS: Record<string, { title: string; tips: string[] }> = {
  summary: {
    title: "Career Objective Tips",
    tips: [
      "Clearly state your years of experience and core expertise.",
      "Short-term goal: What you want to learn and contribute in the next 1-2 years.",
      "Long-term goal: Your direction to become a specialist or manager in 3-5 years.",
      "Avoid generic statements like 'Looking for a dynamic environment'.",
    ],
  },
  experience: {
    title: "Work Experience Tips",
    tips: [
      "Start with strong action verbs: Managed, Designed, Analyzed, Optimized...",
      "Use the formula: Did [Task] using [Tool] resulting in [Outcome/Metric].",
      "Example: 'Optimized Facebook ad campaigns, reducing CPA by 20%'.",
      "Use bullet points (start lines with -) for readability.",
    ],
  },
  skills: {
    title: "Skills Tips",
    tips: [
      "Only list skills directly relevant to the target position.",
      "Separate into Hard Skills (e.g., ReactJS, Figma, SQL) and Soft Skills (Teamwork, Presentation).",
      "Avoid using gauge bars (e.g., 80%, 4/5 stars) as they are subjective.",
    ],
  },
  education: {
    title: "Education Tips",
    tips: [
      "Clearly state school name, major, and attendance period.",
      "You can add GPA (if high, e.g., 3.2/4.0) or notable awards and scholarships.",
    ],
  },
};


// ──────────────────────────────────────────────
// Constants — Theme Map
// ──────────────────────────────────────────────

export const THEME_MAP: Record<string, { name: string; leftBg: string; rightPill: string }> = {
  topcv:         { name: "topcv",         leftBg: "#42312B", rightPill: "#42312B" },
  antuong:       { name: "antuong",       leftBg: "#465345", rightPill: "#465345" },
  thamvong:      { name: "thamvong",      leftBg: "#1A1A1A", rightPill: "#F39C12" },
  makeover_blue: { name: "makeover_blue", leftBg: "#1e3a5f", rightPill: "#2563eb" },
  teal:          { name: "teal",          leftBg: "#0d9488", rightPill: "#0d9488" },
  brown:         { name: "brown",         leftBg: "#5D4037", rightPill: "#5D4037" },
  blue_modern:   { name: "blue_modern",   leftBg: "#1e40af", rightPill: "#1e40af" },
};


// ──────────────────────────────────────────────
// UID Helper
// ──────────────────────────────────────────────

let _uidCounter = 0;
export const genUid = () => `uid_${++_uidCounter}_${Date.now()}`;


// ──────────────────────────────────────────────
// Data Transformation Helpers
// ──────────────────────────────────────────────

/** Split "01/2023 - 06/2025" or "2020 – Present" into { start_date, end_date } */
export const splitPeriod = (period?: string) => {
  if (!period) return { start_date: "", end_date: "" };
  const parts = period.split(/\s*[-\u2013\u2014]\s*/);
  return {
    start_date: parts[0]?.trim() || "",
    end_date: parts[1]?.trim() || "Present",
  };
};


/** Map AI CVMakeoverData JSON → frontend cvData state format */
export function applyAiCvData(aiData: any, fallback: any) {
  const info = aiData.personal_info || {};
  return {
    ...fallback, // Preserve avatar and any other unmapped fields
    full_name: info.name || fallback.full_name || "YOUR NAME",
    position: info.title || fallback.position || "Target Position",
    phone: info.phone || fallback.phone || "",
    email: info.email || fallback.email || "",
    address: info.location || fallback.address || "",
    linkedin: info.linkedin || fallback.linkedin || "",
    summary: info.summary || fallback.summary || "",
    skills: Array.isArray(aiData.skills)
      ? aiData.skills.map((s: string) => `- ${s}`).join("\n")
      : aiData.skills || fallback.skills || "",
    experiences:
      Array.isArray(aiData.experience) && aiData.experience.length > 0
        ? aiData.experience.map((exp: any) => {
            const { start_date, end_date } = splitPeriod(exp.period);
            return {
              _uid: genUid(),
              company_name: exp.company || "",
              position: exp.role || "",
              start_date,
              end_date,
              description: Array.isArray(exp.achievements)
                ? exp.achievements.map((a: string) => `- ${a}`).join("\n")
                : "",
            };
          })
        : fallback.experiences || [],
    educations:
      Array.isArray(aiData.education) && aiData.education.length > 0
        ? aiData.education.map((edu: any) => {
            const { start_date, end_date } = splitPeriod(edu.period);
            return {
              _uid: genUid(),
              school_name: edu.school || "",
              major: edu.degree || "",
              start_date,
              end_date,
            };
          })
        : fallback.educations || [],
  };
}


/** Serialize frontend cvData state → backend CVMakeoverData JSON format */
export function serializeCvDataForBackend(cvData: any) {
  return {
    personal_info: {
      name: cvData.full_name,
      title: cvData.position,
      email: cvData.email,
      phone: cvData.phone,
      linkedin: cvData.linkedin,
      location: cvData.address,
      summary: cvData.summary,
    },
    skills: cvData.skills
      .split("\n")
      .map((s: string) => s.replace(/^- /, ""))
      .filter(Boolean),
    experience: cvData.experiences.map((exp: any) => ({
      company: exp.company_name,
      role: exp.position,
      period: `${exp.start_date} - ${exp.end_date}`,
      achievements: exp.description
        .split("\n")
        .map((a: string) => a.replace(/^- /, ""))
        .filter(Boolean),
    })),
    education: cvData.educations.map((edu: any) => ({
      school: edu.school_name,
      degree: edu.major,
      period: `${edu.start_date} - ${edu.end_date}`,
    })),
    projects: [],
  };
}
