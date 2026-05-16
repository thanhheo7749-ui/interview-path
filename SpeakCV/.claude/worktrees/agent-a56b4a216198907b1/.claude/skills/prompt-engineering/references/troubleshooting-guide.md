---
name: Troubleshooting Guide
description: Common prompt engineering problems and solutions
---

# Prompt Engineering Troubleshooting Guide

Systematic solutions to common LLM failures based on Anthropic workshop insights.

## Diagnostic Framework

When a prompt fails, ask:

1. **What went wrong?** (Symptom)
2. **Why did it happen?** (Root cause)
3. **How to fix it?** (Solution)
4. **How to prevent it?** (Pattern)

## Common Failure Patterns

### 1. Hallucination / Fabricated Details

**Symptom**: Model invents information not present in input data.

**Example**: 
- Input: Accident sketch with unclear vehicle colors
- Output: "The red sedan collided with the blue truck"
- Problem: Colors were never specified

**Root Cause**: No explicit instruction to handle uncertainty.

**Solution**:

```xml
<important_reminders>
1. **Never fabricate details**: If information is not explicitly provided, state "information not available"
2. **Cite evidence**: Reference specific data points for every claim
   Example: "Vehicle A at fault because checkbox 7 is marked"
3. **Distinguish certainty levels**:
   - "Confirmed": Explicitly stated in input
   - "Inferred": Logically derived from evidence
   - "Unknown": Not determinable from available data
</important_reminders>
```

**Prevention Pattern**: Always include uncertainty handling instructions.

---

### 2. Ignoring Instructions

**Symptom**: Model doesn't follow specified steps or format.

**Example**:
- Instruction: "Analyze checkbox form before sketch"
- Output: Starts with sketch interpretation

**Root Cause**: Instructions buried in prose, not visually distinct.

**Solution**:

```xml
<!-- ❌ Buried instructions -->
When you analyze the data, make sure to look at the checkbox form first before interpreting the sketch, as this will give you factual grounding.

<!-- ✅ Clear structure -->
<instructions>
**CRITICAL: Follow this exact sequence:**

1. **Analyze checkbox form FIRST**
   - Extract all marked boxes
   - List factual actions for each vehicle

2. **Interpret sketch SECOND**
   - Use facts from step 1 as guide
   - Match sketch to checkbox data

3. **Determine fault LAST**
   - Cross-reference steps 1 and 2
   - Apply traffic rules
</instructions>
```

**Prevention Pattern**: Use XML tags + numbered steps + bold emphasis for critical instructions.

---

### 3. Inconsistent Output Format

**Symptom**: Response format varies between requests.

**Example**:
- Request 1: Returns JSON
- Request 2: Returns prose
- Request 3: Returns malformed JSON

**Root Cause**: No explicit output structure specified.

**Solution**:

```xml
<output_format>
**REQUIRED FORMAT**: Wrap your final answer in XML tags with JSON inside:

<final_verdict>
{
  "fault": "Vehicle A" | "Vehicle B" | "Both" | "Insufficient Evidence",
  "confidence": "high" | "medium" | "low",
  "evidence": ["specific fact 1", "specific fact 2"],
  "ambiguities": ["unclear element 1", "unclear element 2"]
}
</final_verdict>

**Example**:
<final_verdict>
{
  "fault": "Vehicle A",
  "confidence": "high",
  "evidence": ["checkbox 2 marked (turning right)", "sketch shows A front hit B side"],
  "ambiguities": []
}
</final_verdict>
</output_format>
```

**Advanced**: Use pre-fill to force format:

```python
messages=[
    {"role": "user", "content": prompt},
    {"role": "assistant", "content": "<final_verdict>\n{"}
]
```

**Prevention Pattern**: Provide explicit format + example + pre-fill for critical outputs.

---

### 4. Wrong Analysis Order

**Symptom**: Model jumps to conclusions before gathering evidence.

**Example**:
- Looks at ambiguous sketch first
- Makes premature fault determination
- Ignores contradictory checkbox data

**Root Cause**: No guidance on reasoning sequence.

**Solution**:

```xml
<instructions>
**ANALYSIS SEQUENCE** (do NOT skip or reorder):

Step 1: Evidence Collection
- Read checkbox form completely
- List all marked boxes
- Extract factual statements only

Step 2: Fact Verification
- Cross-check for contradictions
- Note any ambiguities
- Assess data quality

Step 3: Interpretation
- Use facts from Step 1 to guide sketch analysis
- Match visual elements to checkbox data
- Identify points of agreement/disagreement

Step 4: Conclusion
- Apply rules to verified facts
- State confidence level
- Cite specific evidence

**DO NOT** interpret the sketch before completing Step 1.
</instructions>
```

**Prevention Pattern**: Explicit sequence with "do NOT" warnings for common mistakes.

---

### 5. Missing Edge Cases

**Symptom**: Model handles typical cases well but fails on unusual inputs.

**Example**:
- Works: Clear checkbox marks, legible sketch
- Fails: Water-damaged form, partially obscured sketch

**Root Cause**: No examples of ambiguous or damaged data.

**Solution**: Add few-shot examples covering edge cases:

```xml
<examples>
<example type="edge_case">
<scenario>
Form: Water damage obscures Vehicle B checkboxes
Sketch: Clear and detailed
</scenario>

<correct_analysis>
Evidence from form:
- Vehicle A: Checkbox 3 marked (changing lanes)
- Vehicle B: Checkboxes illegible due to water damage

Sketch shows:
- Clear collision at lane boundary
- Vehicle positions suggest lane change collision

Conclusion: Insufficient Evidence
Reasoning: "While the sketch is clear, Vehicle B's actions cannot be determined due to form damage. Cannot assign fault without knowing both vehicles' actions."
</correct_analysis>

<incorrect_analysis>
❌ "Based on the sketch, Vehicle A was changing lanes and hit Vehicle B, so Vehicle A is at fault."
Problem: Assumes Vehicle B's actions without evidence.
</incorrect_analysis>
</example>
</examples>
```

**Prevention Pattern**: Include 2-3 edge case examples with both correct and incorrect responses.

---

### 6. Overly Cautious / Refuses Valid Tasks

**Symptom**: Model expresses excessive uncertainty or refuses reasonable requests.

**Example**:
- Input: Clear checkbox data + clear sketch
- Output: "I cannot determine fault due to potential ambiguities"

**Root Cause**: Tone not specified, model defaults to over-cautious.

**Solution**:

```xml
<task_context>
You are a confident insurance claim analyst. When evidence is clear and unambiguous, state conclusions definitively. Reserve uncertainty only for genuinely unclear cases.

**Confidence guidelines**:
- High confidence: Checkbox + sketch clearly agree → State fault definitively
- Medium confidence: Minor ambiguity in one source → State probable fault with caveat
- Low confidence: Major contradictions or missing data → State insufficient evidence

**Tone**: Professional and decisive. Avoid hedging language ("might", "possibly", "perhaps") when evidence is clear.
</task_context>
```

**Prevention Pattern**: Explicitly set confidence criteria and tone expectations.

---

### 7. Verbose / Inefficient Responses

**Symptom**: Model provides excessive explanation when concise answer needed.

**Example**:
- Expected: JSON verdict
- Received: 3 paragraphs + JSON + additional commentary

**Root Cause**: No brevity instruction or output constraints.

**Solution**:

```xml
<output_format>
Provide ONLY the structured verdict. No preamble, no additional commentary.

<final_verdict>
{
  "fault": "...",
  "confidence": "...",
  "evidence": [...]
}
</final_verdict>

**DO NOT** include:
- Introductory phrases ("Based on my analysis...")
- Explanatory paragraphs
- Closing remarks
- Anything outside the <final_verdict> tags
</output_format>
```

**Advanced**: Use pre-fill to skip preamble entirely.

**Prevention Pattern**: Specify what NOT to include + use pre-fill for production.

---

### 8. Inconsistent Terminology

**Symptom**: Model uses different terms for same concept across responses.

**Example**:
- Response 1: "Vehicle A at fault"
- Response 2: "Driver A responsible"
- Response 3: "Car A caused collision"

**Root Cause**: No terminology standards defined.

**Solution**:

```xml
<terminology_standards>
**REQUIRED TERMS** (use these exact phrases):

- Vehicles: "Vehicle A", "Vehicle B" (never "Car A", "Driver A", "the sedan")
- Fault: "at fault", "not at fault", "insufficient evidence" (never "responsible", "caused", "liable")
- Confidence: "high", "medium", "low" (never "certain", "probable", "unsure")
- Evidence: "checkbox [number] marked", "sketch shows [element]" (always cite specific sources)

**Forbidden terms**: "probably", "might be", "seems like", "appears to"
</terminology_standards>
```

**Prevention Pattern**: Define required terminology + forbidden terms.

---

### 9. Context Window Overflow

**Symptom**: Model loses track of earlier instructions in long prompts.

**Example**:
- Prompt: 10,000 tokens of instructions + examples
- Output: Follows only recent instructions, ignores earlier ones

**Root Cause**: Critical instructions not reinforced at end.

**Solution**:

```xml
<!-- At start of prompt -->
<task_context>
[Initial instructions]
</task_context>

<!-- After long examples/background -->
<important_reminders>
**CRITICAL RULES** (reinforcing key points from above):

1. [Most important rule from task_context]
2. [Second most important rule]
3. [Anti-hallucination reminder]

These rules override any conflicting patterns in examples.
</important_reminders>
```

**Prevention Pattern**: Repeat critical instructions at end of long prompts.

---

### 10. Poor Multi-Modal Integration

**Symptom**: Model analyzes text and images separately, doesn't integrate insights.

**Example**:
- Checkbox says: "Vehicle A turning left"
- Sketch shows: Vehicle A going straight
- Output: Doesn't notice contradiction

**Root Cause**: No instruction to cross-reference modalities.

**Solution**:

```xml
<multi_modal_instructions>
**CRITICAL**: Text and image must agree. Follow this process:

1. **Extract facts from text first**
   - List all checkbox marks
   - Note any text annotations

2. **Analyze image second**
   - Describe visual elements objectively
   - Note any unclear areas

3. **Cross-reference (REQUIRED)**
   - Does image confirm text facts?
   - Any contradictions?
   - If contradiction exists: Flag it explicitly and request clarification

**Example contradiction handling**:
"Checkbox 2 indicates Vehicle A was turning left, but the sketch shows Vehicle A traveling straight. This is a contradiction. Cannot determine fault without resolving this discrepancy."
</multi_modal_instructions>
```

**Prevention Pattern**: Explicit cross-reference step + contradiction handling.

---

## Debugging Workflow

When a prompt fails:

```
1. Identify failure type (use table above)
2. Check if root cause matches known pattern
3. Apply corresponding solution
4. Test on same input
5. If still fails, enable Extended Thinking to see reasoning
6. Extract insights from thinking transcript
7. Add specific instruction to address revealed gap
8. Repeat until success
```

## Quick Diagnostic Table

| Symptom | Likely Cause | Quick Fix |
|---------|-------------|-----------|
| Invents details | No uncertainty handling | Add "if unclear, state unknown" |
| Ignores steps | Instructions not structured | Use XML + numbered steps |
| Wrong format | No format specified | Add `<output_format>` + example |
| Wrong order | No sequence guidance | Add "Step 1, Step 2..." |
| Fails edge cases | No examples | Add few-shot edge cases |
| Too cautious | Tone not set | Define confidence criteria |
| Too verbose | No brevity instruction | Specify "ONLY provide..." |
| Inconsistent terms | No standards | Define required terminology |
| Loses context | Long prompt | Repeat critical rules at end |
| Misses contradictions | No cross-reference | Add explicit integration step |

## Testing Strategy

After applying fixes:

1. **Test on original failure case** (must pass)
2. **Test on 3-5 similar cases** (generalization check)
3. **Test on edge cases** (robustness check)
4. **Test on typical cases** (ensure no regression)

If any test fails, return to debugging workflow.

---

**Remember**: Every failure is a missing instruction. The model isn't broken — the prompt needs refinement.
