# Prompt Engineering Skill

Master prompt engineering using Anthropic's best practices from their "Prompting 101" workshop.

## What This Skill Teaches

This skill provides comprehensive guidance on writing effective prompts for Claude and other LLMs, based on real-world production experience from Anthropic's Applied AI team.

### Core Topics

1. **Context Layer**: Setting up task, role, and tone
2. **Knowledge Layer**: Providing background information and domain knowledge
3. **Structure Layer**: Using XML tags and organized formatting
4. **Execution Layer**: Step-by-step instructions, few-shot examples, and reminders

### When to Use This Skill

Activate this skill when you need to:
- Write or optimize prompts for LLM applications
- Debug hallucinations or accuracy issues
- Structure complex instructions
- Build production AI systems
- Improve model responses
- Handle multi-modal inputs (text + images)

## Skill Structure

```
prompt-engineering/
├── SKILL.md                              # Main skill instructions
└── references/
    ├── quick-start-templates.md          # Ready-to-use prompt templates
    ├── troubleshooting-guide.md          # Common problems and solutions
    └── advanced-techniques.md            # Production optimization patterns
```

## Quick Start

### Basic Prompt Template

```xml
<task_context>
You are a [ROLE] helping [AUDIENCE] with [TASK].
Tone: [TONE]
</task_context>

<background_knowledge>
[Domain-specific information]
</background_knowledge>

<instructions>
1. [Step 1]
2. [Step 2]
3. [Step 3]
</instructions>

<input_data>
[User's data]
</input_data>

<output_format>
[Expected structure]
</output_format>

<important_reminders>
1. [Critical constraint]
2. [Anti-hallucination rule]
</important_reminders>
```

## Key Principles

1. **Context is everything**: Never assume the model "just knows"
2. **Structure beats prose**: Use XML tags for clarity
3. **Order matters**: Guide thinking step-by-step
4. **Examples teach**: Few-shot > lengthy explanations
5. **Iterate relentlessly**: Every failure improves the prompt

## Real-World Case Study

The skill uses a real production example: analyzing Swedish car accident insurance claims with checkbox forms and hand-drawn sketches. This demonstrates:

- Handling multi-modal inputs (forms + images)
- Preventing hallucinations with explicit uncertainty handling
- Structuring complex analysis workflows
- Optimizing for production (caching, pre-fill, output formatting)

## References

### Quick Start Templates
5 ready-to-use templates for common scenarios:
- Data analysis
- Code review/generation
- Content creation
- Customer support
- Multi-modal analysis

### Troubleshooting Guide
Solutions for 10 common failure patterns:
- Hallucinations
- Ignoring instructions
- Inconsistent output
- Wrong analysis order
- Missing edge cases
- And more...

### Advanced Techniques
Production-grade patterns:
- Prompt caching strategy
- Extended thinking optimization
- Pre-fill for output control
- Multi-stage prompting
- Confidence calibration
- Adversarial testing
- Prompt versioning and monitoring

## Installation

This skill is already installed in your project at:
```
.claude/skills/prompt-engineering/
```

To use it in other projects, copy the entire directory to:
```
<project>/.claude/skills/prompt-engineering/
```

Or install globally:
```
cp -r .claude/skills/prompt-engineering ~/.claude/skills/
```

## Usage Examples

### Example 1: Debugging Hallucinations

**Problem**: Model invents details not in input

**Solution**: Add uncertainty handling
```xml
<important_reminders>
If information is not explicitly provided, state "information not available".
Never fabricate details. Cite specific evidence for every claim.
</important_reminders>
```

### Example 2: Enforcing Output Format

**Problem**: Inconsistent response structure

**Solution**: Use output format + pre-fill
```xml
<output_format>
<result>
{
  "field1": "value",
  "field2": "value"
}
</result>
</output_format>
```

```python
# Pre-fill to force format
messages=[
    {"role": "user", "content": prompt},
    {"role": "assistant", "content": "<result>\n{"}
]
```

### Example 3: Improving Accuracy

**Problem**: Model jumps to conclusions

**Solution**: Add step-by-step sequence
```xml
<instructions>
Follow this exact sequence:
1. Extract facts from data
2. Verify facts for contradictions
3. Interpret based on verified facts
4. Draw conclusion with evidence
</instructions>
```

## Testing Your Prompts

1. Test on real data (not synthetic examples)
2. Include edge cases (damaged data, ambiguities)
3. Check for hallucinations
4. Verify output format consistency
5. Measure accuracy on 100+ examples

## Production Deployment

Before deploying:
- [ ] Tested on 100+ real examples
- [ ] Adversarial testing completed
- [ ] Static content positioned for caching
- [ ] Output format strictly enforced
- [ ] Monitoring configured
- [ ] Prompt versioned

## Contributing

Found a useful pattern? Add it to the references:
1. Document the pattern with examples
2. Test on real use cases
3. Add to appropriate reference file

## Credits

Based on the "Prompting 101" workshop by Hannah and Christian from Anthropic's Applied AI team, featuring real-world production insights from insurance claim analysis systems.

## License

This skill is part of the oh-my-claudecode plugin ecosystem.

---

**Remember**: Prompt engineering is experimental science. Test, fail, learn, iterate.
