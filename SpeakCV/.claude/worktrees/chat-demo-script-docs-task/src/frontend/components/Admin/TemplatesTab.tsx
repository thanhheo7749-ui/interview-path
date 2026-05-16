/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

"use client";
import { useEffect, useState } from "react";
import { Briefcase, Plus, Edit2, Trash2, X } from "lucide-react";
import toast from "react-hot-toast";
import {
  getJdTemplates,
  createJdTemplate,
  updateJdTemplate,
  deleteJdTemplate,
} from "@/services/api";

export function TemplatesTab() {
  const [templates, setTemplates] = useState<any[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const res = await getJdTemplates();
      setTemplates(res.templates || []);
    } catch (err) {
      toast.error("Error loading JD list");
    }
  };

  const openModal = (template: any = null) => {
    if (template) {
      setEditingId(template.id);
      setTitle(template.title);
      setDescription(template.description);
    } else {
      setEditingId(null);
      setTitle("");
      setDescription("");
    }
    setIsModalOpen(true);
  };

  const handleSaveJD = async () => {
    if (!title.trim() || !description.trim()) {
      toast.error("Please fill in both title and content!");
      return;
    }
    try {
      if (editingId) {
        await updateJdTemplate(editingId, { title, description });
        toast.success("Updated successfully!");
      } else {
        await createJdTemplate({ title, description });
        toast.success("New JD created successfully!");
      }
      setIsModalOpen(false);
      fetchTemplates();
    } catch (err) {
      toast.error("Error saving JD!");
    }
  };

  const handleDeleteJD = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this JD?")) return;
    try {
      await deleteJdTemplate(id);
      toast.success("JD template deleted!");
      fetchTemplates();
    } catch (err) {
      toast.error("Error deleting JD!");
    }
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4">
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-3xl font-bold text-white">JD Template Library</h2>
        <button
          onClick={() => openModal()}
          className="flex items-center bg-yellow-600 hover:bg-yellow-500 text-white px-5 py-2.5 rounded-xl font-bold transition-all shadow-lg shadow-yellow-600/20"
        >
          <Plus size={18} className="mr-2" /> Add New JD
        </button>
      </div>

      <div className="bg-slate-900/80 backdrop-blur-md border border-slate-700 rounded-3xl overflow-hidden shadow-2xl">
        <div className="p-6 border-b border-slate-800 bg-slate-800/30">
          <h3 className="text-xl font-bold text-white flex items-center gap-2">
            <Briefcase className="text-yellow-400" /> Manage interview content
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-950 text-slate-400 text-xs uppercase tracking-widest font-bold">
                <th className="p-5 border-b border-slate-800 w-1/4">
                  Position Title
                </th>
                <th className="p-5 border-b border-slate-800 w-2/4">
                  JD Content
                </th>
                <th className="p-5 border-b border-slate-800 w-1/4 text-right">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {templates.length === 0 ? (
                <tr>
                  <td
                    colSpan={3}
                    className="p-8 text-center text-slate-500 italic"
                  >
                    No JD templates yet. Click "Add New JD"!
                  </td>
                </tr>
              ) : (
                templates.map((tpl) => (
                  <tr
                    key={tpl.id}
                    className="hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="p-5 font-bold text-white">{tpl.title}</td>
                    <td className="p-5 text-slate-400 text-sm">
                      <div className="line-clamp-2">{tpl.description}</div>
                    </td>
                    <td className="p-5 text-right">
                      <button
                        onClick={() => openModal(tpl)}
                        className="text-blue-400 hover:text-blue-300 p-2.5 bg-blue-400/10 hover:bg-blue-400/20 rounded-xl mr-2 transition-colors"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        onClick={() => handleDeleteJD(tpl.id)}
                        className="text-red-400 hover:text-red-300 p-2.5 bg-red-400/10 hover:bg-red-400/20 rounded-xl transition-colors"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-slate-700 w-full max-w-2xl rounded-3xl shadow-2xl overflow-hidden flex flex-col">
            <div className="flex justify-between items-center p-6 border-b border-slate-800 bg-slate-950/50">
              <h3 className="text-xl font-bold text-white flex items-center gap-2">
                <Briefcase className="text-yellow-400" size={20} />
                {editingId ? "Edit JD Template" : "Create New JD Template"}
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white bg-slate-800 p-2 rounded-full transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-8 flex flex-col gap-6">
              <div>
                <label className="block text-sm font-bold text-slate-300 mb-2 uppercase tracking-wider">
                  Position title
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-5 py-3.5 text-white font-medium focus:outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 transition-all"
                  placeholder="Enter position title..."
                />
              </div>
              <div>
                <label className="block text-sm font-bold text-slate-300 mb-2 uppercase tracking-wider">
                  Detailed description (JD)
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-5 py-4 text-white h-56 resize-none focus:outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 transition-all custom-scrollbar leading-relaxed"
                  placeholder="Paste JD content here..."
                />
              </div>
            </div>

            <div className="p-6 border-t border-slate-800 bg-slate-950/50 flex justify-end gap-3">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-6 py-3 rounded-xl font-bold text-slate-300 hover:bg-slate-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveJD}
                className="px-6 py-3 rounded-xl font-bold bg-yellow-600 hover:bg-yellow-500 text-white shadow-lg shadow-yellow-600/20 transition-all"
              >
                {editingId ? "Save changes" : "Create New JD"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
