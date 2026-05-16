const apiKey = import.meta.env.VITE_GEMINI_API_KEY;
const model = import.meta.env.VITE_GEMINI_MODEL || 'gemini-2.5-flash-preview-09-2025';

export const fallbackPolishResult = {
  feedback:
    'Your answer is understandable, but it is too general. Use the STAR method to explain the situation, task, action, and result more clearly.',
  polishedAnswer:
    'In my previous project, our team had a tight deadline before the final demo. I reviewed the backend API, tested each endpoint, and coordinated with the frontend member to fix integration issues. As a result, we completed the demo on time and delivered a stable feature.',
};

export const fallbackQaAnswer =
  'InterviewPath is different because it does not stop at interview practice. It creates an AI Candidate Passport that stores candidate readiness, feedback, and hiring history across the full recruitment journey.';

async function callGeminiAPI(prompt, systemInstruction, useJsonFormat = false) {
  if (!apiKey) return null;

  const payload = {
    contents: [{ parts: [{ text: prompt }] }],
    systemInstruction: { parts: [{ text: systemInstruction }] },
  };

  if (useJsonFormat) {
    payload.generationConfig = {
      responseMimeType: 'application/json',
      responseSchema: {
        type: 'OBJECT',
        properties: {
          feedback: { type: 'STRING' },
          polishedAnswer: { type: 'STRING' },
        },
        required: ['feedback', 'polishedAnswer'],
      },
    };
  }

  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    );

    if (!response.ok) return null;

    const data = await response.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) return null;

    return useJsonFormat ? JSON.parse(text) : text;
  } catch {
    return null;
  }
}

export async function polishAnswer(rawAnswer) {
  const systemInstruction =
    'You are a recruiter coach. Review the answer and rewrite it professionally using the STAR method. Return concise JSON with feedback and polishedAnswer.';

  const result = await callGeminiAPI(`Answer: ${rawAnswer}`, systemInstruction, true);
  return result?.feedback && result?.polishedAnswer ? result : fallbackPolishResult;
}

export async function answerJudgeQuestion(question) {
  const systemInstruction =
    'You are the AI co-founder of InterviewPath. Answer a pitch competition judge concisely in two confident sentences.';

  const result = await callGeminiAPI(question, systemInstruction, false);
  return result || fallbackQaAnswer;
}
