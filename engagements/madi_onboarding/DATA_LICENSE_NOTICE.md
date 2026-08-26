# Data license notice — MaDI-Bench

This engagement benchmarks against the **Companies** task of the Mannheim Data
Integration Benchmark (MaDI-Bench).

- **Source:** https://github.com/wbsg-uni-mannheim/MaDI-Bench
- **Paper:** *MaDI-Bench: An End-to-End Data Integration Benchmark*, University of
  Mannheim (Bizer group), arXiv:2606.30371 — verified on arXiv as published under
  **CC BY-NC-ND 4.0** (Attribution — NonCommercial — NoDerivatives).
- **Data license: not separately stated by the authors.** The GitHub repository
  has no `LICENSE` file, no `license` field in `pyproject.toml`, and no `license`
  key in `CITATION.cff`; the README and project website do not address data terms
  either (checked via the GitHub API and the rendered site, 2026-08-26). The
  CC BY-NC-ND 4.0 badge is arXiv's license for the *paper submission*, not a
  confirmed statement about the benchmark data's own terms — treating the two as
  identical would be an unverified claim, not evidence.

## What that means for this repo

- **Absent an explicit data license, this repo treats the data as at least as
  restricted as the paper: non-commercial, no redistribution of derived copies.**
  That is the conservative reading, not a confirmed license — if the authors
  publish explicit data terms, update this notice to match them.
- **The data is never committed here**, consistent with that conservative
  reading: `engagements/madi_onboarding/data/` is gitignored and populated only by
  `download_data.py`, which fetches the pinned files from the official repository
  and verifies each against its git blob SHA-1.
- **Difficulty variants** come from MaDI-Bench's own `easy/`, `medium/`, `hard/`
  directories — this project does not generate its own corruptions of their data.
- The dev-flywheel loop code in this repo is Apache-2.0 and unaffected either way;
  only the downloaded benchmark files are in question.

## Reproducibility without redistribution

The synthetic fixtures under `fixtures/` (invented companies) are this project's
own content and are used for all tests and CI — nothing under `fixtures/` comes
from MaDI-Bench. To fetch the real benchmark data, run
`uv run python engagements/madi_onboarding/download_data.py`, then convert each
source's CSV to the ingest format with
`uv run python engagements/madi_onboarding/csv_to_ingest.py --source forbes`
(one JSON object per row, columns verbatim — no MaDI-specific field mapping;
that happens in `adapters/<source>.toml`, the onboarding step this engagement
demonstrates).

If you use this benchmark, cite the MaDI-Bench paper (`CITATION.cff` in the
upstream repository).
