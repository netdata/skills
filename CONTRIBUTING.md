# Contributing

Full guide comes in v0.1.0 Phase 7. Minimum rules for now:

1. Every skill must pass `python scripts/validate.py`.
2. Every skill follows the layout in `docs/skill-authoring-guide.md`.
3. No em-dashes in prose. No banned phrases (see `scripts/validate.py`).
4. Accuracy first, brevity second, style third. Cite sources for version-specific claims.
5. If your change affects instrumentation code that the E2E test exercises, update the sample app in the same PR so the fixture and the skill stay in sync.
