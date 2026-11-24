# ticket488 — reconcile Nova goal status through PR #487

PR: [#488 — docs: reconcile Nova goal evidence through PR #487](https://github.com/Bepoadewale/davdeploy/pull/488) (draft)
Branch: `docs/nova-status-through-487`

## Goal

Refresh the canonical project, backlog, implementation, composed-goal, and
capability evidence documents to match current GitHub and verified test state.
Record PR #485 and #487 as merged, retain PR #486's open review/clean-room
status accurately, and distinguish exact-shape isolated customer-side evidence
from Nova dispatch and hosted execution.

## Acceptance criteria

- [ ] Current backend main, hosted release, open PRs, and required CI evidence
  match GitHub.
- [ ] PRs #485 and #487 and their direct AWS lifecycle evidence are recorded
  with exact-shape limits and cleanup results.
- [ ] PR #486's unresolved clean-room gate and protected local artifacts remain
  explicit; no cleanup is claimed.
- [ ] The 26 architecture entries and 30 Terraform roots remain intact, with
  the direct lifecycle evidence mapped only to tested shapes.
- [ ] The goal owner's acceptance of isolated same-account lifecycle evidence
  remains clear and separate from Nova-dispatch evidence.
- [ ] Documentation conventions, matrix integrity, and diff checks pass;
  required PR CI passes before merge.
- [ ] No AWS resource, hosted control-plane resource/state/lock, feature gate,
  or protected local file is changed.

## Boundaries

Documentation only. Do not touch the hosted control plane, Terraform state or
locks, AWS workload resources, or protected local artifacts. Preserve all
historical evidence and do not claim Nova has deployed a customer workload.
