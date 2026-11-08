/*
 * Copyright (c) 2026 SpeakCV Team
 * This project is licensed under the MIT License.
 * See the LICENSE file in the project root for more information.
 */

import { useState, useEffect } from "react";
import { getJdTemplates } from "@/services/api";

interface JdTemplatePickerProps {
  onPick: (description: string) => void;
  className?: string;
}

export function JdTemplatePicker({ onPick, className }: JdTemplatePickerProps) {
  const [templates, setTemplates] = useState<any[]>([]);

  useEffect(() => {
    getJdTemplates()
      .then((data) => setTemplates(data.templates || []))
      .catch((err) => console.log("Error loading JD templates:", err));
  }, []);

  const handleSelectTemplate = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedId = parseInt(e.target.value);
    const selectedTemplate = templates.find((t) => t.id === selectedId);
    onPick(selectedTemplate ? selectedTemplate.description : "");
  };

  return (
    <select
      className={
        className ||
        "w-full bg-white border border-slate-200 p-2.5 rounded-lg text-sm text-slate-700 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-200 cursor-pointer"
      }
      onChange={handleSelectTemplate}
      defaultValue=""
    >
      <option value="" disabled>
        -- Select a JD template (Optional) --
      </option>
      <option value="">Custom Input</option>
      {templates.map((tpl) => (
        <option key={tpl.id} value={tpl.id}>
          {tpl.title}
        </option>
      ))}
    </select>
  );
}
