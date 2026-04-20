# Pull Request

## Summary

<!-- One or two sentences on what changed and why. -->

## Scope

<!-- Check one. -->

- [ ] New skill
- [ ] Edit to an existing skill
- [ ] Infrastructure (scripts, CI, docs)
- [ ] Bug fix

## Checklist

- [ ] `python scripts/validate.py` passes locally.
- [ ] No em-dashes in prose.
- [ ] No banned phrases (see CONTRIBUTING.md).
- [ ] New or changed facts are cited against a source in the Netdata repo or an upstream doc.
- [ ] Skill frontmatter `description` starts with "Use when" and fits under 1024 characters.
- [ ] Every H2 required by the skill template is present.
- [ ] If the change affects instrumentation code that the E2E test exercises, the sample app in `tests/e2e/sample-apps/` was updated in the same PR to keep it in sync.

## Evidence

<!-- Paste validator output, test output, or a link to a green CI run. -->
