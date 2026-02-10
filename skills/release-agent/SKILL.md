---
name: release-agent
description: Validates release readiness by running checks, verifying docs, and summarizing risks. Use before merging to main or cutting a release.
---

# Release Agent

## Overview
Validate project readiness before merge or release.

## Workflow
1. Run full tests and linting if available.
2. Verify docs, versioning, and changelog where applicable.
3. Summarize readiness, risks, and required follow-ups.

## Outputs
- Readiness summary
- List of blockers and risks
