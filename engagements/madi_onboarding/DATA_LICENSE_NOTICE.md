# Data license notice — MaDI-Bench

This engagement benchmarks against the **Companies** task of the Mannheim Data
Integration Benchmark (MaDI-Bench).

- **Source:** https://github.com/wbsg-uni-mannheim/MaDI-Bench
- **Paper:** *MaDI-Bench: An End-to-End Data Integration Benchmark*, University of
  Mannheim (Bizer group), arXiv:2606.30371
- **License:** the MaDI-Bench data is **CC BY-NC-ND 4.0**
  (Attribution — NonCommercial — NoDerivatives).

## What that means for this repo

- **The data is never committed here.** NoDerivatives forbids redistributing a
  reshaped or subsetted copy, so `engagements/madi_onboarding/data/` is gitignored
  and populated only by `download_data.py`, which fetches the pinned files from the
  official repository and verifies each against its git blob SHA-1.
- **Difficulty variants** come from MaDI-Bench's own `easy/`, `medium/`, `hard/`
  directories — this project does not generate its own corruptions of their data.
- **NonCommercial:** the benchmark data may be used for non-commercial purposes
  only. The dev-flywheel loop code in this repo is Apache-2.0 and unaffected; the
  benchmark data retains its own license.

## Reproducibility without redistribution

The synthetic fixtures under `fixtures/` (invented companies) are this project's
own content and are used for all tests and CI. To run the loop against the real
benchmark, run `python engagements/madi_onboarding/download_data.py` — it is the
checksum-pinned, reproducible substitute for committing the data.

If you use this benchmark, cite the MaDI-Bench paper.
