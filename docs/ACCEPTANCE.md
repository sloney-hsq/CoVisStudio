# Local acceptance index

## Current integrated application — 2026-11-13

The current entry is **http://127.0.0.1:8066/**. `start.ps1`, `python -m backend` and `scripts/serve_studio.py` all use the same backend and `frontend/dist`. The former idle 8066 process was replaced only after its empty session was checked and exported; older review services and records were retained.

- `traces/integration-fix-20261113/verification-index.json`: source/build fingerprints, checks and evidence boundaries.
- `traces/integration-fix-20261113/backend-final.txt`: **217 passed** after the credential fix; the earlier 215-pass run is retained in `backend-tests.txt`. Existing Starlette/httpx warning remains.
- `traces/integration-fix-20261113/frontend-tests.txt`, `frontend-build.txt`: **25 passed** and built; existing ECharts size advisory remains.
- `traces/integration-fix-20261113/audio-before-complete.txt`, `audio-after.txt`: four reproduced audio lifecycle/capture failures and their passing regressions. The first unfinished reproduction output is also retained.
- `traces/release-browser/20261113-115820-763976/report.json`: four assigned business tasks and ten browser checks, including JSON/CSV and 1920/2560/3840 CSS widths.
- `traces/assigned-voice/20261113-115505-511592/report.json`: direct and bound_revision native transport paths, real Olist/tool/render/playback and pending human scores.
- `traces/live-harness-local/20261113-115505-525590/report.json`: offline spoken input, 8.055 seconds of complete speech and 8.280 seconds of transmitted PCM, twelve local checks passed.

The playback-interruption report and service startup check are linked from the verification index. Successful tool/voice decisions above are local fixtures. One later real connection attempt is retained at `traces/live-browser/20261113-120939-580704/report.json`: HTTP 401 before any input or output. Its diagnosis and file-priority correction are documented in PROVIDERS.md. The corrected credential choice was not retried. The local rejection check retains the original HTTP 401 and closes in 0.250 seconds, with no remote call. Human review and participant effectiveness remain pending. A Windows Proactor reset warning in the first interruption run is retained in its log.

Following the user's process-cleanup request, the idle main app and all earlier CoVis review processes were stopped after exporting their state. Ports listed in earlier records identify historical verification services, not currently running applications. Source, traces and archives are retained.

## Earlier revision build — 2026-11-13

Review **http://127.0.0.1:8060/**. This isolated process uses real Olist and explicitly disabled remote model endpoints. The previous 8050 process was not restarted. Start/reproduction commands are in README.md.

- `traces/revision-build-20261113/python-tests.txt`: complete Python regression for the current build.
- `traces/revision-build-20261113/frontend-tests.txt`, `frontend-build.txt`: unit checks and staged production build.
- `traces/revision-build-20261113/browser/20261113-121215/report.json`: twelve real-browser checks, historical subset references, target scope, reranking, controls, nodes/Undo/Restore, report export, three 4K scaling layouts.
- `traces/revision-build-20261113/browser/20261113-121215/bound-session.json`: actual successful edit and pending human review; evidence and apply events each counted once.
- `traces/revision-study-20261113/summary.json`: 18 authored Olist reference trajectories and six intentionally wrong/recovered scoring cases. This is not a model success rate.
- `traces/revision-model-20261113/confirmation-final-tests.txt`: local native voice protocol, historical read, preview/apply, blocked self-confirmation, spoken confirmation via a new proposal, and superseded-work checks.
- `traces/browser-voice/20261113-041316-699112/report.json`: current staged frontend, real browser PCM/JPEG/tool/render/WebAudio path with a local scripted peer. Synthetic tones and scripted transcription do not establish recognition or human hearing.

Screenshots are in the browser report folder: `historical-subset-selection.png`, `bound-review-pending.png`, and `workspace-*` / `revision-*`. The first browser assertion failure remains in `browser/20261113-120603/`; it was ordered-list comparison where membership was the contract. Earlier provider-test failures and all trial artifacts also remain available.

The browser voice run passed its assertions and exited successfully, but Windows emitted a Proactor `ConnectionResetError` callback during local connection teardown. Its full output is retained in `traces/revision-build-20261113/browser-voice.txt`. The existing Starlette/httpx deprecation and ECharts chunk-size advisory are also retained; no suppression or fallback layer was added.

The first frontend rebuild used the existing dist folder before review isolation was established; subsequent builds and 8060 use `traces/revision-build-20261113/frontend-dist`. We did not restart the existing 8050 session. No paid API or credential loading was performed by the review server or verification scripts.

## Earlier build records

The earlier implementation remains available at http://127.0.0.1:8050/. The following paths document earlier checks, not acceptance of the current revision code.

## Inspect first

- `traces/browser-verification/workspace-2560-scale1.5.png`: 4K screenshot at150% display scaling.
- `traces/browser-verification/workspace-3840-scale1.png`: native4K layout.
- `traces/browser-verification/version-details-1920.png`: source change and historical charts.
- `traces/browser-voice/20261112-191857-244152/`: final browser voice test, screenshots, video, input/output media and a report.
- `traces/provider-integration/`: text/voice/cancel-before-commit protocol evidence.
- `traces/study-verification/summary.json`: task feasibility with explicit interpretation limits.

Raw file timestamps follow the execution host's clock; the project progress date follows the client-provided2026-11-13 date. Clock domains are not silently converted into experimental timing measurements.

## Reproduce

1. Run the backend on8050 using `start.ps1` or the README command.
2. Run `.venv\Scripts\python.exe scripts\verify_browser.py` to exercise the real UI and manual tools. This replaces the active test workspace; use it outside a participant session.
3. Run `.venv\Scripts\python.exe scripts\verify_browser_voice.py` for a separate8052 browser run with a local scripted peer. No credential is read and no remote API is called.
4. Run the Python/frontend commands in README for regressions and build.

The browser voice script sends real test PCM and chart images, but the peer's transcript and tool decision are authored. Audio replay is a test tone. Human review cannot be marked passed on this basis.
