# Contributing

Branch feature/fix work from `dev`. Stable releases use `main` and signed `vX.Y.Z` tags. Keep identifiers, public documentation and user-facing output in English. Update CHANGELOG.md for visible changes.

Preserve premium RoFormer models and ensemble capabilities. Never silently replace a model, reduce model context, change precision or move CUDA work to CPU. Surface memory/device failures with actionable recovery choices.

Validate changes first with the smallest relevant check, then run the required CI checks. Changes to model/runtime/audio behavior need actual processing; metadata fixtures and mocks do not establish inference or playback correctness. Keep adviser findings grounded in current source; implementation remains the primary agent's responsibility.

The schema in `engine/separator_engine/schema.py` is the source of truth. IPC stdout contains only versioned NDJSON; upstream output goes to bounded logs. Do not add shell interpolation, global package installation, broad process termination, or deletion of user recordings.

See BUILDING.md for commands, DESIGN.md for visual conventions, and docs/UPDATE_RULES.md for protected data.
