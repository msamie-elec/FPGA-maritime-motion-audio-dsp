# GitHub staging and release checklist

**Repo:** `msamie-elec/FPGA-maritime-motion-audio-dsp` (private at time of
preparation). **Target:** standalone `release/maritime-av-evidence-2026-11-23`
branch. Do not tag or merge before reviewing the actual staged source.

## What is kept on the release branch

- One native Vivado project: `hardware/build/maritime_a7.xpr`.
- Synthesizable RTL, Arty A7 XDC, self-checking SystemVerilog testbenches and
  vector fixtures under `hardware/`.
- Full GUI and host processing source, cross-platform and Windows scripts.
- Distinct model-level, HDL-level and system-level verification code.
- Concise current engineering reports and public-safe assessment plots.
- Regression CI workflow and license. The FPGA/host boundary is explicitly
  explained.

## What is NOT automatically uploaded

- `hardware/build` generated Vivado runs, temporary caches, bitstreams and
  local debug files; XSim waveforms and local `.Xil` state.
- Original full Windows Vivado report archives that may disclose personal
  absolute paths. The **sanitised parsed metrics** remain.
- Raw serial and test-machine logs which may disclose PC details, unless
  individually reviewed; local ZIP retains evidence separately.
- `.mp4` sources/results and uncertain-licence illustrations (user must
  confirm rights first), including original maritime footage.
- Live environment credentials, tokens and serial-port configuration.

## Publishing the prepared source safely

The release package contains `scripts/prepare_github_release.ps1`. It copies
only the source/review allowlist to a fresh Git checkout, prints the diff and
will **not push until explicitly invoked with `-Push`**. The branch is separate
from `main` and the older feature branches, so no existing history is deleted.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_github_release.ps1
# Inspect the staged folder's changes, then:
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_github_release.ps1 -Push
```

A GitHub credential or authorised GitHub session on the laptop is required
for cloning/pushing the private repository. Do not share passwords or tokens.

## Verification required before declaring a published release

- Ensure the `main`/feature relationship is intentional: release branch is
  not automatically merged.
- CI host tests pass; XSim/system verified in the owner's 23-Nov local build,
  not reproduced by the GitHub CI host.
- Check README and diagrams for precise FIR-versus-host attribution.
- Review every tracked file for source licences, absolute user paths and PII.
- Upload original physical-machine CSV/JSON to the **local evidence archive**;
  attach sanitised summaries to public documentation as appropriate.
- Only tag a final release after changes and links are checked on GitHub.


## RevI release evidence (23 November 2026)

- The source-safe archive includes `evidence/xadc_2026-11-23/` with all 36
  operator-provided XADC snapshots and their provenance/limitations.
- The complete engineering archive additionally includes raw owner-uploaded
  Vivado reports, an earlier failed soak log, and private demonstration clips.
  Keep the raw uploads off public GitHub until paths and media rights are reviewed.
- Use the updated PowerShell publishing script, which recognises an existing
  remote staging branch; confirm its `RELEASE_BRANCH_PUSHED` output and then
  verify the remote tree.
- **Do not merge without reviewing GitHub Actions and the release diff.**
