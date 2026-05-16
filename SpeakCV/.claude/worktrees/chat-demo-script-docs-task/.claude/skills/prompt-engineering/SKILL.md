---
name: prompt-engineering
description: Write effective prompts for Claude and LLMs using Anthropic best practices. Use when creating prompts, optimizing LLM interactions, building AI applications, debugging hallucinations, structuring complex instructions, or improving model accuracy. Covers context setup, XML tags, chain-of-thought, few-shot examples, output formatting, and production optimization.
triggers:
  - write a prompt
  - optimize prompt
  - improve prompt
  - create system prompt
  - LLM hallucinating
  - model not understanding
  - structure prompt
  - prompt engineering
  - better AI responses
  - Claude instructions
tags:
  - prompting
  - llm
  - ai
  - optimization
  - best-practices
---

# Prompt Engineering: Anthropic Best Practices

Master prompt engineering through systematic application of Anthropic's proven techniques. This skill teaches how to write prompts that eliminate hallucinations, improve accuracy, and optimize production LLM applications.

## Core Philosophy

Prompt engineering is **experimental science**: communicate clearly, provide context, iterate based on failures. Never assume the model "just knows" — explicit instructions beat implicit assumptions.

## The Anatomy of an Effective Prompt

Every production-grade prompt has four layers:

```
1. CONTEXT LAYER    → Who is Claude? What's the task? What tone?
2. KNOWLEDGE LAYER  → Background info, domain knowledge, constraints
3. STRUCTURE LAYER  → XML tags, formatting, data organization
4. EXECUTION LAYER  → Step-by-step instructions, examples, reminders
```

## 1. Context Layer: Task & Tone

**Always start by establishing:**

- **Role**: What is Claude's function?
- **Task**: What specific job needs doing?
- **Tone**: How should Claude behave?

### Example: Insurance Claim Analysis

```xml
<task_context>
You are an AI assistant helping insurance claim adjusters review Swedish car accident reports. Your role is to analyze checkbox forms and hand-drawn accident sketches to determine fault.

Maintain a factual, confident tone. If evidence is unclear or sketches are illegible, state uncertainty explicitly. Never guess or fabricate details. Only conclude fault when evidence is definitive.
</task_context>
```

**Why this works:**
- Defines scope (insurance claims, not general accidents)
- Sets expectations (factual, not speculative)
- Prevents hallucination (explicit uncertainty handling)

## 2. Knowledge Layer: Background Information

Provide domain knowledge the model needs but cannot derive from input alone.

### System Prompt Strategy

Put **static, reusable knowledge** in the system prompt to leverage **Prompt Caching**:

```xml
<form_structure>
The Swedish accident report contains 17 checkbox rows:
- Rows 1-8: Vehicle A actions (turning left, turning right, changing lanes, etc.)
- Rows 9-16: Vehicle B actions (same categories)
- Row 17: Additional notes

Checkmarks may appear as:
- X marks
- Circles
- Scribbles or dots
- Any mark indicating selection

Column layout:
- Left column: Vehicle A
- Right column: Vehicle B
</form_structure>
```

**Caching benefits:**
- Faster processing (cached content reused)
- Lower costs (cached tokens cheaper)
- Consistent interpretation across requests

### When to Use System vs User Prompts

| System Prompt | User Prompt |
|---------------|-------------|
| Static rules, schemas, domain knowledge | Variable input data |
| Tone, role, constraints | Specific questions, requests |
| Examples (few-shot) | Current task context |
| Never changes per request | Changes every request |

## 3. Structure Layer: XML Tags & Organization

Claude responds exceptionally well to structured data. Use XML tags to create clear boundaries.

### XML Tag Benefits

```xml
<!-- ❌ Unstructured -->
Here's the user's preference: they want detailed analysis but skip obvious details.
Also they prefer bullet points over paragraphs.

<!-- ✅ Structured -->
<user_preferences>
  <analysis_depth>detailed</analysis_depth>
  <skip>obvious details</skip>
  <format>bullet points</format>
</user_preferences>
```

**Why XML tags work:**
- Clear semantic boundaries
- Easy reference in instructions ("Check <user_preferences> before responding")
- Enables extraction and validation
- Reduces ambiguity

### Recommended Tag Patterns

```xml
<task_context>...</task_context>           <!-- Role and objectives -->
<background_knowledge>...</background_knowledge>  <!-- Domain info -->
<input_data>...</input_data>               <!-- Variable user data -->
<instructions>...</instructions>           <!-- Step-by-step process -->
<examples>...</examples>                   <!-- Few-shot demonstrations -->
<output_format>...</output_format>         <!-- Expected response structure -->
<important_reminders>...</important_reminders>  <!-- Critical constraints -->
```

## 4. Execution Layer: Guiding Model Thinking

### A. Step-by-Step Instructions (Chain of Thought)

**Order matters.** Guide Claude through analysis in logical sequence:

```xml
<instructions>
Follow this exact sequence:

1. **Analyze the checkbox form first**
   - Identify which boxes are marked for Vehicle A
   - Identify which boxes are marked for Vehicle B
   - List the actions each vehicle was taking

2. **Extract factual events**
   - Create a bullet list of confirmed facts from checkboxes
   - Note any ambiguities or unclear marks

3. **Interpret the sketch last**
   - Use facts from step 1 to guide sketch interpretation
   - Match vehicle positions to reported actions
   - Identify points of impact

4. **Determine fault**
   - Cross-reference sketch with checkbox data
   - Apply traffic rules to the scenario
   - State conclusion with supporting evidence
</instructions>
```

**Why sequence matters:**
- Prevents premature conclusions from ambiguous sketches
- Builds evidence foundation before interpretation
- Mirrors human expert reasoning process

### B. Few-Shot Examples

For complex or edge-case scenarios, provide examples with reasoning:

```xml
<examples>
<example>
<scenario>
Vehicle A: Checkbox 2 marked (turning right)
Vehicle B: Checkbox 5 marked (going straight)
Sketch: Shows collision at intersection, Vehicle A's front hits Vehicle B's side
</scenario>

<analysis>
Facts from form:
- Vehicle A was turning right
- Vehicle B was going straight

Sketch interpretation:
- Impact point confirms A turned into B's path
- B had right of way going straight

Conclusion: Vehicle A at fault
Evidence: "Vehicle A marked checkbox 2 (turning right) and the sketch shows A's front colliding with B's side, indicating A failed to yield while turning."
</analysis>
</example>

<example>
<scenario>
Vehicle A: Checkbox 3 marked (changing lanes)
Vehicle B: No clear marks visible (form damaged)
Sketch: Illegible, water damage obscures details
</scenario>

<analysis>
Facts from form:
- Vehicle A was changing lanes
- Vehicle B's actions unknown (form damaged)

Sketch interpretation:
- Cannot interpret due to water damage

Conclusion: Insufficient evidence
Reasoning: "While Vehicle A was changing lanes (checkbox 3), Vehicle B's actions are unknown due to form damage, and the sketch is illegible. Cannot determine fault without clear evidence."
</analysis>
</example>
</examples>
```

**Few-shot best practices:**
- Include both clear-cut and ambiguous cases
- Show reasoning process, not just answers
- Demonstrate how to handle uncertainty
- Use real data formats (Base64 images in production)

### C. Important Reminders (Anti-Hallucination)

End with critical constraints to prevent common failures:

```xml
<important_reminders>
1. **Always cite evidence**: Reference specific checkboxes or sketch elements
   Example: "Vehicle A at fault because checkbox 7 (ran red light) is marked"

2. **Never fabricate details**: If sketch is unclear, state "sketch illegible" 
   Do NOT guess vehicle colors, weather, or details not in the data

3. **Distinguish certainty levels**:
   - "Definitive": Clear checkbox + clear sketch agreement
   - "Probable": Checkbox clear but sketch ambiguous
   - "Insufficient": Missing or contradictory data

4. **No assumptions about Swedish traffic law**: Only use rules explicitly provided in <background_knowledge>
</important_reminders>
```

## Production Optimization

### Output Formatting

Control response structure for downstream processing:

```xml
<output_format>
Provide your analysis in two parts:

1. **Reasoning** (for human review): Full chain-of-thought analysis

2. **Structured verdict** (for database): Wrap in XML tags
<final_verdict>
{
  "fault_determination": "Vehicle A" | "Vehicle B" | "Both" | "Insufficient Evidence",
  "confidence": "high" | "medium" | "low",
  "key_evidence": ["checkbox 2 marked for A", "sketch shows A front hit B side"],
  "ambiguities": ["sketch partially obscured in top-right corner"]
}
</final_verdict>
</output_format>
```

### Pre-filled Responses

Force specific output format by pre-filling Claude's response:

```python
# API call with pre-fill
response = client.messages.create(
    model="claude-opus-4-7",
    messages=[
        {"role": "user", "content": "Analyze this claim..."},
        {"role": "assistant", "content": "<final_verdict>\n{"}  # Pre-fill
    ]
)
```

**Effect**: Claude MUST continue from `{"`, ensuring valid JSON output without preamble.

### Extended Thinking

For complex analysis, enable Extended Thinking mode:

```python
response = client.messages.create(
    model="claude-opus-4-7",
    thinking={
        "type": "enabled",
        "budget_tokens": 10000
    },
    messages=[...]
)
```

**Benefits:**
- Claude uses internal "scratchpad" for reasoning
- More accurate on complex logic
- Thinking transcript reveals model's analysis process

**Optimization loop:**
1. Enable Extended Thinking
2. Review thinking transcript for insights
3. Extract key reasoning patterns
4. Add those patterns to system prompt
5. Disable Extended Thinking (now unnecessary)
6. Result: Same accuracy, lower cost

## Common Failure Patterns & Fixes

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Hallucinated details | No explicit uncertainty handling | Add "If unclear, state 'insufficient evidence'" |
| Ignores instructions | Instructions buried in text | Use XML tags + numbered steps |
| Inconsistent format | No output structure specified | Provide `<output_format>` + pre-fill |
| Wrong analysis order | No sequence guidance | Add explicit "Step 1, Step 2..." instructions |
| Misses edge cases | No examples of ambiguity | Add few-shot examples with unclear data |
| Overly cautious | Tone not specified | Set confident tone in `<task_context>` |

## Iterative Optimization Process

Prompt engineering is experimental. Follow this loop:

```
1. Write initial prompt
2. Test on real data
3. Identify failure cases
4. Add specific instructions/examples for failures
5. Re-test
6. Repeat until accuracy acceptable
```

**Key principle**: Every failure reveals a missing instruction. Don't blame the model — improve the prompt.

## Checklist for Production Prompts

Before deploying:

- [ ] Task and tone clearly defined in `<task_context>`
- [ ] All necessary background knowledge in system prompt
- [ ] Static content positioned for Prompt Caching
- [ ] XML tags used for all structured data
- [ ] Step-by-step instructions in logical order
- [ ] Few-shot examples for edge cases
- [ ] Explicit uncertainty handling ("if unclear, then...")
- [ ] Anti-hallucination reminders at end
- [ ] Output format specified with examples
- [ ] Tested on real failure cases
- [ ] Pre-fill used if strict format required

## Real-World Application Template

```xml
<task_context>
[Define role, task, and tone]
</task_context>

<background_knowledge>
[Domain info, schemas, rules - cache this]
</background_knowledge>

<instructions>
1. [First analysis step]
2. [Second analysis step]
3. [Final step]
</instructions>

<examples>
[2-3 few-shot examples with reasoning]
</examples>

<input_data>
[Variable user data goes here]
</input_data>

<output_format>
[Specify exact structure, use XML tags for extraction]
</output_format>

<important_reminders>
1. [Critical constraint 1]
2. [Anti-hallucination rule]
3. [Uncertainty handling]
</important_reminders>
```

## Advanced Techniques

### Multi-Modal Prompting

When working with images (like accident sketches):

```xml
<image_analysis_instructions>
1. Describe what you see objectively first
2. Note any unclear or damaged areas
3. Only then interpret based on checkbox data
4. If interpretation conflicts with checkboxes, trust checkboxes
</image_analysis_instructions>
```

### Confidence Calibration

Teach Claude to self-assess:

```xml
<confidence_criteria>
High confidence: Checkbox data + sketch clearly agree
Medium confidence: Checkbox clear but sketch ambiguous OR vice versa
Low confidence: Contradictory data or missing information
Report "Insufficient Evidence" if confidence is low
</confidence_criteria>
```

### Prompt Compression

After optimization, compress verbose instructions:

```xml
<!-- Before -->
If the sketch is not clear enough to determine the exact position of the vehicles, you should state that the sketch is unclear rather than making assumptions about where the vehicles were located.

<!-- After -->
Unclear sketch → state "sketch illegible", never assume positions
```

## Key Takeaways

1. **Context is everything**: Never assume the model knows the task
2. **Structure beats prose**: XML tags > unstructured text
3. **Order matters**: Guide thinking step-by-step
4. **Examples teach**: Few-shot > lengthy explanations
5. **Iterate relentlessly**: Every failure improves the prompt
6. **Cache strategically**: Put static knowledge in system prompt
7. **Control output**: Use pre-fill + XML for structured data
8. **Prevent hallucination**: Explicit uncertainty handling + evidence citation

---

**Remember**: Prompt engineering is not a formula — it's experimental science. Test, fail, learn, iterate.
