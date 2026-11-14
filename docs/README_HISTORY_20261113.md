# Historical implementation notes

This is the previous README, retained as version-specific history. Follow the current root README and research protocol for current behavior. Raw traces mentioned below are local-only and are not distributed.

# CoVis Studio

## Current reranking repair and real image-input verification

The two explicitly authorized Qwen Realtime diagnostics now both pass: reranking all three
MG views (39.937 s) and reusing historical members in the selected service views (27.906 s).
Complete input utterances were 4.24/8.08 s and 4.24/6.64 s, with no retries or new TTS calls.
Both new revision-7 JPEGs were verified byte-for-byte in actual native image messages,
after matching rendering/capture and before the next model response. Final reply audio
completed naturally. See [repair and evidence](docs/RERANK_REPAIR.md) and the
[real results and playback](traces/rerank-repair-20261113/real-two/RESULTS.md).

The model-facing `top_n` is explicitly a positive decimal string, compiled once into the
unchanged strict domain integer. Raw and compiled arguments are recorded separately;
manual edits retain numeric fields. This is a declared shared tool-contract change, not
a permissive fallback. Earlier failed calls below remain failed. These two authored cases
do not estimate participant effects; image delivery does not prove visual reasoning or
human comprehension. Human listening remains pending.

## Subsequent authorized real API check

The current revision flow was tested once against real Qwen Realtime. Charts 2/3 changed
from January–June to January–March during actual assistant playback, preserving MG,
historical members, measures and chart 1. All 21 archived chart queries matched independent
SQL; both post-commit image sequences were verified. The original result remains **failed**:
18/19 checks passed, but the 32.08-second final audio had played only 28.72 seconds when the
budget stopped it. Connection including setup/cleanup was 56.109 seconds; inputs were 8.56
and 6.32 seconds, without retries or new TTS calls. See
[the actual result and playback entry](traces/route-real-validation/RESULTS.md).
Independent human intent coding and listening remain pending. This authored bound_revision
case is not a formal participant result or treatment-effect estimate. Test services were closed.

## Current delivery: revision support and independent study scoring

The [implementation guide](docs/REVISION_STUDY_DELIVERY.md) connects three normal paths:
request/record correctness, an inline **Sources / Change / Keep & release** summary,
and independent intent coding → locked interpretation → SQL verification → formal report.
The same execution, saved sets and basic Apply/Modify controls remain in both study conditions.

In **Experiment**, choose **Formal study · business decisions** for the eight new `study_*`
materials. Both assigned conditions use one explicit Realtime window (up to 60 seconds)
within the 480-second task. Charts and the six-field written response remain available afterward.
The original `exp_*` authored diagnostics keep their fixed goals and historical reports.

In an archived attempt, **Independent intent review** prepares a blinded input packet and
blank coding templates. Two human codings and an explicit adjudication must be locked
before independent SQL scoring; the primary endpoint includes the terminal task state.
Formal reports use the first actually begun assigned participant attempt, preserve repeats,
and retain missing/unknown outcomes. No participant results or human listening are supplied
by software. Material review and formal-study approval remain pending. This delivery calls
no paid model or TTS service. Start normally with `start.ps1`; opening the UI opens no provider.

## Latest model, interface and research review

See [the code/design review](docs/MODEL_CODE_DESIGN_REVIEW.md) and [the research claim review](docs/RESEARCH_CLAIM_REVIEW.md). The current implementation closes superseded native tool calls, preserves truthful prior-commit receipts, waits for the committed chart's actual browser capture before live-voice tool continuation, and avoids resending the same frame. The participant interface and revision-card values are clearer at 1920/2560/3840 CSS widths.

Two earlier authorized Qwen tests are archived separately in `traces/deep-review/real-two-20261113/`: historical-set transfer succeeded; reranking failed because the model returned a string count against the acknowledged integer schema. The fresh-image repair initially had local browser verification only; the subsequent route validation and current reranking checks above add real-provider transport evidence. Calls used complete cached natural speech, under 10 seconds per utterance and under 60 seconds per connection, without retries. No runtime service is intentionally left running after testing.

The [Chinese manuscript](paper/cscwd_zh/main-rerank.pdf) and [English manuscript](paper/cscwd_en/main.pdf) are synchronized six-page review drafts. Both distinguish prior diagnostics, the two new cases, local repairs and the prospective user study. The updated Chinese PDF uses a new filename because another application holds its previous output open. Source and build files are in [the bilingual package](paper/CoVisStudio_CSCWD_Bilingual.zip), whose standard Chinese `main.pdf` contains the verified new version. No user benefit is inferred from these authored API checks.

## Current research execution

Follow [the completion plan](docs/RESEARCH_EXECUTION_PLAN.md). The latest local update repairs observed VAD-fragment association and the late cancelled-tool-turn sequence, aligns direct/bound analytical instructions, and prepares outcome-blinded intent-coding packets. Controlled application parity and a 24-check browser revision flow pass; real acceptance of the repaired native sequence and human outcomes remain pending. No extra paid calls were made.

## Latest real diagnostic results

The authorized eight-case matrix is complete: four final goals were correct and their revision audio played naturally; raw driver status is three passes and five failures because one correct trial crossed the watchdog during shutdown. All connections were under 60 seconds, no automatic retry occurred, and originals remain intact. See [findings and next research steps](docs/REAL_API_FINDINGS.md) and `traces/real-study-20261113-224313/RESULTS.md`. These authored tests are not participant or frozen B0/B2 results. Earlier local-only and two-failure statements below describe their earlier delivery stages.

An English-language workspace for revising analytical dashboards with an AI. Built for a 27-inch 4K display, including 150% and 200% Windows scaling. Independent of VerbalVis and DuplexVisEval; all chart values come from real Olist queries.

The research mechanism separates **historical evidence** from **current edit targets**. You can reuse the categories in an earlier RJ chart in a current MG analysis without restoring the earlier region, dates or metrics. Direct editing has the same history and saved-category-set tools. The [unified research protocol](docs/UNIFIED_RESEARCH_PROTOCOL.md) governs the next B0/B2 study design; the existing [experiment protocol](docs/EXPERIMENT_PROTOCOL.md) documents the earlier apparatus. Direct and bound revision now share concrete candidate resolution and the same compiler. Application inputs use archived evidence packages; native provider history and participant intent scoring still require study-level decisions before formal comparison.

The [execution update](docs/GOAL_EXECUTION.md) addresses the two observed real-call failures: `revise_analysis` uses flat arguments to compute and commit an explicit analytical revision in one call, and each conversation turn displays its own actual execution outcome. A spoken answer without a commit displays **No chart changes**. Prior successful receipts stay with their original request. The new behavior is locally verified; the earlier failed real trials are retained and have not been rerun.

The [Jarvis adaptation](docs/JARVIS_ADAPTATION.md) adds AudioWorklet output-sample receipts, dual-time evidence packages, exact outgoing model-input archives, shared evidence candidates, and separate execution/delivery review. It extends Stage 1 correlated event records, calibrated browser/server timestamps and chart render/exposure observations. Speech onset still immediately revokes old publication permission and stops playback before upstream cancellation. See [implementation and function relationships](docs/STAGE1_IMPLEMENTATION.md). These observations do not establish acoustic listening, comprehension, a frozen native model context, or experimental benefit. This delivery uses local verification only, with `qwen3.8-omni-flash-realtime` preserved as the configured real voice model.

## Start the current application

Open **http://127.0.0.1:8066/**. This is the current application entry, not an older review build.

```powershell
cd C:\CoVisStudio
.\start.ps1
```

`start.ps1` builds `frontend/dist` and starts the current backend on 8066. For an already-built frontend:

```powershell
.\.venv\Scripts\python.exe -m backend
# Explicit configuration, if you keep your key in another file:
.\.venv\Scripts\python.exe -m backend --env-file C:\path\to\study.env
```

`scripts/serve_studio.py` calls the same launcher. It no longer serves a dated build under `traces/`. Frontend development uses `npm run dev` in `frontend`, with same-origin `/api` and `/ws` proxied to 8066. The server supports one active laboratory workspace.

At the user's request, the idle app and earlier review servers were stopped after verification. Run the command above when you want to use the interface again.

Fresh installation uses Python 3.11+ and Node 20+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
npm --prefix frontend ci
.\start.ps1
```

## Configure Qwen

Fill `QWEN_API_KEY=` in **`C:\CoVisStudio\.env.local`**, then restart the server. This file is ignored. The interface reports only whether a key exists, never the key itself. The default text and voice models are `qwen3.8-omni-flash` and `qwen3.8-omni-flash-realtime`; workspace URLs are in `.env.example`.

Opening the application does not contact a model. Text connects when you send a request; voice connects when you choose **Start speaking**. There is no automatic retry, reconnect or paid startup check.

The explicitly selected file may also use `DASHSCOPE_API_KEY`, as DuplexVisEval and VerbalVis do. A file declaring either credential field takes precedence over process credentials, including an intentionally blank local value. Keys are never copied between projects. The user authorized reading the existing DuplexVisEval configuration:

```powershell
.\start.ps1 -EnvFile C:\DuplexVisEval\.env.local
```

The earlier real attempt returned HTTP 401 before any JPEG, PCM, tool execution or model reply. File precedence was fixed afterward. Two newly authorized real attempts on November 13 successfully connected using the explicitly selected DuplexVisEval key; both failed their analytical goals. The original failure remains recorded. This project's own `.env.local` is still blank. See `traces/real-two-cases/20261113-213538/RESULTS.md` for the new evidence.

An explicitly authorized one-shot test is prepared:

```powershell
.\.venv\Scripts\python.exe scripts\verify_live_browser.py --run-real
```

This older script uses Windows offline speech and one PTT connection; it does not establish live-overlap performance. The current two-case driver is `scripts/verify_two_real_cases.py`, consuming complete neural speech files prepared by `scripts/prepare_natural_test_speech.py`. Real calls require explicit `--run-real` and an authorized configuration; do not rerun the recorded attempts automatically. The latest input uses Qwen-Audio 3.1 TTS Flash / Abby_v3.1 with natural brisk delivery. Every source segment is under ten seconds; the live microphone also transmits silence between segments, which is reported separately.

## Use the workspace

1. Choose **Start with Olist** or a business task to create real-query charts. The default workspace is empty.
2. Select chart numbers or data marks, then edit directly, type, or speak. The current rendered canvas and exact selection accompany the request.
3. Open **Journey** to inspect an earlier version. **Use as evidence** references its categories; **Restore this canvas** is a separate operation.
4. Use **Saved sets** to save and reuse exact category members in every condition. Evidence-linked revision additionally shows the affected current views, changed conditions and retained conditions in a revision card.
5. Inspect the actual chart-action receipt: a preview, required confirmation, committed change and failed edit are different states. A model's sentence is not proof of a chart update.
6. **Committed** means the backend published that version; **Displayed** requires the browser's matching chart-render receipts. **No chart changes** means that request made no chart commit, and does not imply that an ordinary discussion was incorrect. **Review edit** opens the existing local editor and makes no model call.

**Text**, **Push to talk** and **Live voice** share tools and visual context. PTT stops at ten seconds of captured PCM in the audio worklet. Paused input is excluded from the next recording. Live voice continues receiving microphone input during assistant playback; sessions close after the sixty-second development budget. **Stop speaking** stops current playback without cancelling chart work; **Cancel** revokes unfinished work.

Image status distinguishes local capture, queued frames and actual native image-buffer delivery. In PTT, a chart image generated after submission waits for the next real audio input. Delivery does not prove that the model inspected that image before speaking. See [the provider contract](docs/PROVIDERS.md).

## Assigned tasks, records and review

Open **Experiment**, enter a pseudonymous participant ID and allocation slot, then prepare and begin the assigned task. Each participant receives four business families, with two direct and two evidence-linked trials. Eight materials provide two versions per family; structural matching has been checked, human difficulty equivalence has not.

The task timer starts only on **Begin task**. Participants submit a conclusion, supporting evidence, category origin and calculation scope. A later chart edit marks a saved answer stale. Finishing retains the actual outcome, including incomplete, abandoned and timed-out work. The eight-minute task limit does not enlarge the sixty-second development voice budget.

Review an exact attempt from **Experiment** to inspect its chart versions, transcript, recordings, events and automatic report. Coding drafts append separately; original records are not rewritten. Technical chart correctness, response completeness, human interpretation, repair coding and listening remain separate fields. JSON/CSV retain all attempts and explicit missing assignments; human judgments stay pending until reviewed.

New application records are under **`traces/studio/<session-id>/`**. Existing review archives remain available and unchanged. See [the coding guide](docs/REVIEW_CODING.md) and [matched materials](docs/MATCHED_TASKS.md).

## Data and supported tools

Olist is read from `C:/VerbalVis/datasets/olist/data` without importing or modifying the old project. Orders use distinct order membership; revenue excludes freight; low-review rate uses canonical scores 1–2 over valid scored orders; delivery time uses one eligible order weight. Rate denominators are retained. Fixed members and dynamic ranking are different operations. Numeric values cannot be overwritten manually.

Six chart forms are supported in this study: bar, line, area, pie, aggregate scatter and single-row heatmap. Pie requires additive values. This scoped project does not claim all ten graphic types from the older benchmark.

| Shared tools | Purpose |
| --- | --- |
| `revise_analysis` | Primary flat-argument analytical edit: reuse evidence or preserve current members, change explicit fields, and compute/commit through the shared compiler in one call; unresolved choices remain previews |
| `read_dashboard`, `read_history` | Inspect public current and historical evidence |
| `create_chart`, `edit_charts`, `remove_charts` | Compute and publish exact chart changes |
| `set_dashboard`, `arrange_charts` | Change dashboard title and arrangement |
| `save_category_set`, `list_category_sets`, `apply_category_set` | Deterministically reuse members in every condition |
| `list_evidence_candidates`, `apply_evidence_candidate` | Choose a real chart/set ID and apply its exact members in either main condition |
| `preview_revision`, `apply_revision` | Prepare and apply an evidence/current-scope revision |

All edits use private candidates, actual Olist calculations and versioned commits. See [CONTRACT.md](docs/CONTRACT.md) for schemas and [TASKS.md](TASKS.md) for current results and remaining work.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts\verify_release_browser.py
.\.venv\Scripts\python.exe scripts\verify_assigned_voice.py
.\.venv\Scripts\python.exe scripts\verify_live_browser_local.py
.\.venv\Scripts\python.exe scripts\verify_playback_revision.py
```

The browser checks use isolated local services and preserve their records in `traces/`. Local scripted providers test the actual transport and tools, not recognition or model intelligence. The [acceptance index](docs/ACCEPTANCE.md) links current and older evidence.

**Remaining evidence:** real endpoint acceptance with the corrected credential selection and semantic performance, human listening and interpretation, and participant-level method comparisons. Live voice currently supersedes unfinished work on a new utterance; it does not distinguish backchannels. No result here proves full-duplex superiority or that evidence-linked revision beats the strong saved-set baseline.

Keep credentials, Olist CSVs, traces, audio and participant identities private and out of source commits.
#   C o V i s S t u d i o 
 
 