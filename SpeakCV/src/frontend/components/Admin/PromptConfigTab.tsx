/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";
import { useEffect, useState } from "react";
import {
  getSystemConfig,
  updateSystemConfig,
  uploadAIBrainFile,
  createAIBrainIngestionJob,
  getAIBrainIngestionJob,
  applyAIBrainDraft,
  publishAIBrainVersion,
  getAIBrainVersions,
  assembleAIBrainPrompt,
} from "@/services/api";
import { Save, Settings2, Loader2, Cpu, UploadCloud, GitBranchPlus } from "lucide-react";
import toast from "react-hot-toast";
import { BrainGraphPanel } from "./BrainGraphPanel";

export function PromptConfigTab() {
  const [systemPrompt, setSystemPrompt] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [aiEnableBrainRetrieval, setAiEnableBrainRetrieval] = useState(true);
  const [aiBrainIngestionEnrichmentEnabled, setAiBrainIngestionEnrichmentEnabled] = useState(true);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [versionName, setVersionName] = useState("2026.05.15-mvp");
  const [ingesting, setIngesting] = useState(false);
  const [jobId, setJobId] = useState("");
  const [jobData, setJobData] = useState<any>(null);
  const [publishing, setPublishing] = useState(false);
  const [versions, setVersions] = useState<any[]>([]);
  const [assemblePreview, setAssemblePreview] = useState("");

  const loadVersions = async () => {
    try {
      const res = await getAIBrainVersions();
      setVersions(res.versions || []);
    } catch {
      setVersions([]);
    }
  };

  const handleRunIngestion = async () => {
    if (!selectedFile) {
      toast.error("Please choose a file (.txt, .md, .docx)");
      return;
    }
    try {
      setIngesting(true);
      const uploaded = await uploadAIBrainFile(selectedFile);
      const job = await createAIBrainIngestionJob(uploaded.file_key, versionName.trim() || undefined);
      setJobId(job.job_id);
      localStorage.setItem("aiBrainLastJobId", job.job_id);
      const detail = await getAIBrainIngestionJob(job.job_id);
      setJobData(detail);
      toast.success("Ingestion job created successfully");
      await loadVersions();
    } catch (err: any) {
      toast.error(err.message || "Failed to run ingestion");
    } finally {
      setIngesting(false);
    }
  };

  const handleRefreshJob = async () => {
    if (!jobId) return;
    try {
      const detail = await getAIBrainIngestionJob(jobId);
      setJobData(detail);
    } catch (err: any) {
      toast.error(err.message || "Failed to refresh job");
    }
  };

  const handleApplyDraft = async () => {
    if (!jobId) {
      toast.error("No ingestion job selected");
      return;
    }
    try {
      const res = await applyAIBrainDraft(jobId, 0.65);
      toast.success(`Applied: ${res.accepted_nodes} nodes, ${res.accepted_edges} edges`);
      await handleRefreshJob();
    } catch (err: any) {
      toast.error(err.message || "Failed to apply draft");
    }
  };

  const handlePublish = async () => {
    if (!versionName.trim()) {
      toast.error("Version is required");
      return;
    }
    try {
      setPublishing(true);
      await publishAIBrainVersion(versionName.trim());
      toast.success("Version published");
      await loadVersions();
    } catch (err: any) {
      toast.error(err.message || "Publish failed");
    } finally {
      setPublishing(false);
    }
  };

  const handleAssemblePreview = async () => {
    try {
      const res = await assembleAIBrainPrompt({
        version: versionName.trim() || undefined,
        job_role: "Backend Engineer",
        seniority: "Senior",
        interview_mode: "technical",
        skill_tags: ["python", "system-design"],
      });
      setAssemblePreview(res.prompt || "");
    } catch (err: any) {
      toast.error(err.message || "Assemble prompt failed");
    }
  };


  useEffect(() => {
    loadVersions();
    const lastJobId = localStorage.getItem("aiBrainLastJobId");
    if (lastJobId) {
      setJobId(lastJobId);
      getAIBrainIngestionJob(lastJobId)
        .then((detail) => setJobData(detail))
        .catch(() => {
          localStorage.removeItem("aiBrainLastJobId");
          setJobData(null);
        });
    }
  }, []);

  useEffect(() => {
    getSystemConfig()
      .then((res) => {
        setSystemPrompt(res.system_prompt);
        setTemperature(res.temperature);
        setAiEnableBrainRetrieval(res.ai_enable_brain_retrieval !== false);
        setAiBrainIngestionEnrichmentEnabled(res.ai_brain_ingestion_enrichment_enabled !== false);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching configuration:", err);
        toast.error("Cannot load system configuration");
        setLoading(false);
      });
  }, []);

  const handleSave = async () => {
    try {
      setSaving(true);
      await updateSystemConfig(
        systemPrompt,
        temperature,
        aiEnableBrainRetrieval,
        aiBrainIngestionEnrichmentEnabled
      );
      toast.success("AI configuration updated successfully!");
    } catch (err: any) {
      toast.error(err.message || "Error updating configuration");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64 text-slate-400">
        <Loader2 className="animate-spin mr-3 text-blue-500" size={28} />
        Loading system configuration...
      </div>
    );
  }

  return (
    <div className="animate-fade-in relative max-w-[92vw] xl:max-w-[1600px] mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h2 className="text-3xl font-black text-white flex items-center gap-3">
            <Cpu className="text-purple-500" size={32} />
            AI Prompt Configuration
          </h2>
          <p className="text-slate-400 mt-2 text-sm font-medium">
            Prompt engineering settings for the AI interviewer
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-3 rounded-xl font-bold transition-all shadow-lg shadow-purple-500/20 disabled:opacity-50 flex items-center gap-2"
        >
          {saving ? (
            <Loader2 className="animate-spin" size={18} />
          ) : (
            <Save size={18} />
          )}
          Save Configuration
        </button>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl relative space-y-8">
        {/* SYSTEM PROMPT BLOCK */}
        <div>
          <label className="flex items-center gap-2 text-lg font-bold text-slate-200 mb-3">
            <Settings2 size={20} className="text-purple-400" />
            Base Guardrail Prompt (v2)
          </label>
          <p className="text-xs text-slate-500 mb-4">
            Used together with active Brain version output and interview metadata
            (Job Position and Interview Mode) before sending to the AI model.
          </p>
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            className="w-full h-80 bg-slate-800 text-slate-200 border border-slate-700 rounded-xl p-5 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all font-mono text-sm leading-relaxed"
            placeholder="Enter base AI system prompt..."
          />
        </div>

        <div className="pt-4 border-t border-slate-800/80">
          <label className="flex items-center justify-between text-lg font-bold text-slate-200 mb-4">
            <span>Enable Brain Retrieval</span>
            <button
              type="button"
              onClick={() => setAiEnableBrainRetrieval((v) => !v)}
              className={`px-3 py-1 rounded-lg text-sm font-semibold ${aiEnableBrainRetrieval ? "bg-emerald-600 text-white" : "bg-slate-700 text-slate-200"}`}
            >
              {aiEnableBrainRetrieval ? "ON" : "OFF"}
            </button>
          </label>
          <p className="text-xs text-slate-500">
            Toggle GraphRAG retrieval context in runtime chat flow.
          </p>
        </div>

        <div className="pt-4 border-t border-slate-800/80">
          <label className="flex items-center justify-between text-lg font-bold text-slate-200 mb-4">
            <span>Enable Ingestion Enrichment</span>
            <button
              type="button"
              onClick={() => setAiBrainIngestionEnrichmentEnabled((v) => !v)}
              className={`px-3 py-1 rounded-lg text-sm font-semibold ${aiBrainIngestionEnrichmentEnabled ? "bg-emerald-600 text-white" : "bg-slate-700 text-slate-200"}`}
            >
              {aiBrainIngestionEnrichmentEnabled ? "ON" : "OFF"}
            </button>
          </label>
          <p className="text-xs text-slate-500">
            Toggle LLM enrichment for Interviewer Brain ingestion candidates.
          </p>
        </div>

        {/* TEMPERATURE BLOCK */}
        <div className="pt-4 border-t border-slate-800/80">
          <label className="flex items-center justify-between text-lg font-bold text-slate-200 mb-4">
            <div className="flex items-center gap-2">
              <span className="text-blue-400">🌡️</span> Temperature (Creativity)
            </div>
            <span className="text-purple-400 bg-purple-500/10 px-3 py-1 rounded-lg">
              {temperature.toFixed(1)}
            </span>
          </label>
          <p className="text-xs text-slate-500 mb-6">
            0.0: Deterministic, precise responses | 1.0: Creative, diverse
            responses. Recommended for AI interview: 0.5 - 0.7.
          </p>
          <div className="flex items-center gap-6">
            <span className="text-slate-400 font-bold">0.0</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-purple-500 transition-all hover:accent-purple-400"
            />
            <span className="text-slate-400 font-bold">1.0</span>
          </div>
        </div>

        {/* AI BRAIN INGESTION BLOCK */}
        <div className="pt-6 border-t border-slate-800/80 space-y-4">
          <h3 className="text-lg font-bold text-slate-200 flex items-center gap-2">
            <GitBranchPlus size={18} className="text-emerald-400" />
            Interviewer Brain Ingestion (MVP)
          </h3>

          <div className="grid lg:grid-cols-12 gap-4">
            <div className="lg:col-span-3 space-y-4">
              <div className="grid md:grid-cols-2 lg:grid-cols-1 gap-4">
                <div>
                  <label className="text-xs text-slate-400 block mb-2">Brain version</label>
                  <input
                    value={versionName}
                    onChange={(e) => setVersionName(e.target.value)}
                    className="w-full bg-slate-800 text-slate-200 border border-slate-700 rounded-xl px-4 py-2 text-sm"
                    placeholder="2026.05.15-mvp"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-2">Upload file (.txt, .md, .docx)</label>
                  <input
                    type="file"
                    accept=".txt,.md,.docx"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="w-full bg-slate-800 text-slate-200 border border-slate-700 rounded-xl px-3 py-2 text-sm file:mr-3 file:rounded file:border-0 file:bg-slate-700 file:text-slate-200 file:px-3 file:py-1"
                  />
                </div>
              </div>

              <div className="grid sm:grid-cols-2 gap-3">
                <button
                  onClick={handleRunIngestion}
                  disabled={ingesting}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-xl font-semibold disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {ingesting ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}
                  Upload & Parse
                </button>
                <button
                  onClick={handleRefreshJob}
                  disabled={!jobId}
                  className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-xl font-semibold disabled:opacity-40"
                >
                  Refresh Job
                </button>
                <button
                  onClick={handleApplyDraft}
                  disabled={!jobId}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-xl font-semibold disabled:opacity-40"
                >
                  Apply Draft
                </button>
                <button
                  onClick={handlePublish}
                  disabled={publishing}
                  className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-xl font-semibold disabled:opacity-50"
                >
                  {publishing ? "Publishing..." : "Publish Version"}
                </button>
                <button
                  onClick={handleAssemblePreview}
                  className="sm:col-span-2 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-xl font-semibold"
                >
                  Preview Prompt
                </button>
              </div>

              <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4 text-sm text-slate-300 space-y-2">
                <div><span className="text-slate-400">Job:</span> {jobData?.job_id || "Not selected"}</div>
                <div><span className="text-slate-400">Status:</span> {jobData?.status || "-"}</div>
                <div><span className="text-slate-400">Summary:</span> {JSON.stringify(jobData?.summary || {})}</div>
              </div>
            </div>

            <div className="lg:col-span-9 space-y-3">
              <BrainGraphPanel candidates={jobData?.candidates || []} />
              <div className="text-xs text-slate-400">
                Overview: {(jobData?.summary?.nodes || 0)} nodes · {(jobData?.summary?.edges || 0)} edges
              </div>

              {jobData && (
                <div className="max-h-44 overflow-auto custom-scrollbar bg-slate-800/40 border border-slate-700 rounded-xl p-3">
                  {(jobData.candidates || []).slice(0, 16).map((c: any) => (
                    <div key={c.id} className="text-xs py-1 border-b border-slate-700/60">
                      #{c.id} [{c.kind}] conf={Number(c.confidence || 0).toFixed(2)} - {c.payload?.label || c.payload?.type || "candidate"}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>


          {assemblePreview && (
            <div>
              <label className="text-xs text-slate-400 block mb-2">Assembled prompt preview</label>
              <textarea
                value={assemblePreview}
                readOnly
                className="w-full h-48 bg-slate-800 text-slate-200 border border-slate-700 rounded-xl p-4 font-mono text-xs"
              />
            </div>
          )}

          <div className="text-xs text-slate-500">
            Existing versions: {versions.map((v: any) => `${v.version} (${v.status})`).join(" | ") || "None"}
          </div>
        </div>
      </div>
    </div>
  );
}
