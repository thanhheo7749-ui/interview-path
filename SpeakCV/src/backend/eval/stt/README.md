# Speech-to-text benchmark

This tool decides, on the team's own recordings, which speech-to-text provider to use for accented Vietnamese and
Korean speech. It ships with no audio and no results. The decision gate stays open until the team records clips and
runs it with a real provider key.

## Record the clips

- 10 to 15 clips in total, with at least 4 per language you plan to support (Vietnamese `vi`, Korean `ko`, English `en`).
- Clean conditions first: a quiet room, a normal microphone, 5 to 20 seconds each, natural interview-style sentences.
- Include the regional and foreign accents your candidates actually have.
- Formats: `.webm` (what the browser records), `.wav`, `.mp3` or `.m4a`.
- Put the files in `eval/stt/clips/`. Everything there except `.gitkeep` is git-ignored, so no voice data enters the repo.
  Only record people who agreed to it.

## Write `eval/stt/clips/manifest.yaml`

```yaml
clips:
  - file: vi-01.webm
    language: vi          # sent to the provider as the language hint
    reference: "Tôi muốn xin nghỉ phép năm."   # exactly what was said
    seconds: 8            # optional; improves the cost estimate
  - file: ko-01.webm
    language: ko
    reference: "연차 휴가를 신청하고 싶습니다."
```

Case, spacing and punctuation are ignored when comparing, so write the reference naturally.

## Run it

```
make eval-stt                         # uses the providers in your environment, asks before spending
make eval-stt ARGS=--dry-run          # prints the estimate and stops
make eval-stt ARGS=--yes              # accepts the estimate without asking
make eval-stt ARGS="--profile fake"   # tests the tool only: measures nothing
```

The run prints a cost estimate first and calls no provider until you confirm. Reports go to `eval/reports/` as
`stt-<provider>-<timestamp>.md` and `.json` (git-ignored; commit a chosen one with `git add -f`).

## The decision gate

The metric is the character error rate (CER): edit distance over the reference length, after Unicode NFKC, lower
casing, and removing spaces and punctuation. Per language, the average must be at or below 15% (`GATE_CER = 0.15`) on
clean clips.

- Every language at or below 15%: the provider passes. Record the report with the decision.
- Any language above 15%: stop and consult the owner before building on that provider. Do not loosen the gate or
  drop the failing language to get a pass.

A fake-provider report says it measures nothing. Never quote its numbers.
