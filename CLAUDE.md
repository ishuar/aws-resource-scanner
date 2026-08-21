# CLAUDE.md

**aws-resource-inventory** — Python CLI that inventories AWS resources
across regions/services (boto3, typer, rich). Entry points:
`aws-inventory`, `aws-resource-inventory`.

## Product context

- Today: a read-only multi-region, multi-service **inventory** scanner
  with tag filtering (Resource Groups Tagging API path).
- Next: **`aws-inventory waste`** — find resources still generating
  costs but no longer used. `PRODUCT.md` is the spec of record: the
  `Finding` type, the `SignalProvider` seam, v1 rules, roadmap, and the
  decision log. Product guarantees (non-negotiable): read-only forever,
  zero setup, evidence with honest confidence levels.

## Non-negotiable engineering rules

1. **Best practice over workaround — always.** Fix the cause, not the
   symptom. If a tool's default is wrong for us, configure it explicitly
   and say why in a comment; never patch around it silently. Transitional
   measures must be named as such and completed.
2. **Explicit over implicit configuration.** Tool behaviour must never
   change as a side effect of a version bump. Example: `ruff.lint.select`
   is pinned in pyproject because ruff's built-in defaults drift between
   releases. Expanding a rule set is its own deliberate PR.
3. **Test-first for every behaviour change.** Write the failing test,
   confirm it is red, then fix. Update only the tests that pin the
   behaviour being deliberately changed.
4. **Pure refactors ship with zero test edits.** If a refactor needs a
   test change, it is not a refactor — split the PR.
5. **One concern per PR.** Version bumps, behaviour changes, refactors,
   and lint migrations never share a diff.
6. **PR titles are release notes.** Squash-merge titles land verbatim in
   the release-please changelog, so a title must describe the change in
   words any user understands — never internal codenames or session
   shorthand ("candidate 3", "part 1 of 3", "the wave"). Same for PR
   descriptions: what changed, why, and how it was verified.
7. **Don't hand-roll what the platform provides.** botocore's adaptive
   retry mode owns transient-error retries (the old retry_with_backoff
   wrapper is deleted — do not reintroduce one). Same instinct applies to
   pagination (use paginators, always) and diffing.
8. **Unused features get deleted, not fixed.** `--compare`/deepdiff were
   removed after proving zero successful executions (the locked deepdiff
   couldn't even be imported). Apply the deletion test with evidence
   before investing in a fix.
9. **Every scanning client comes from
   `aws_scanner_lib.clients.get_scan_client`** — never `session.client()`
   directly. It owns pool size, timeouts, adaptive retries, the
   creation lock (boto3 sessions are not thread-safe for client
   creation), and the `aws-resource-inventory` user-agent stamp.
10. **Verify merges against real AWS**: `scripts/e2e-diff.sh` (no args)
   fetches origin and compares `origin/main~1` vs `origin/main` scan
   output. Run it after merging anything that touches scan behaviour;
   add `--tag-key/--tag-value` to cover the Resource Groups tag path.
11. **Squash merges + stacked PRs**: after a squash lands, rebase any
    dependent branch onto main (`git rebase --onto main <old-base>`).
12. **Keep it simple; readable beats clever.** The simplest design that
    works wins. Code a maintainer can't follow in one read gets
    simplified, not documented around. Complexity must buy something
    measurable, and the burden of proof is on the complexity.
13. **Features get grilled before they get built.** "Makes sense" is not
    a spec. Every new feature starts with a grilling session
    (`/grilling`): walk the decision tree, one question at a time, and
    record the outcome in `PRODUCT.md`'s decision log before writing
    code. This applies even more to features that seem obviously good.
14. **Two real implementations before an abstraction.** Don't introduce
    a seam, interface, or config knob for a hypothetical second case.
    Registry dicts over plugin frameworks (`services/registry.py` is the
    house pattern). One adapter is a hypothetical seam; two make it real.

## Python style

- Type hints on every public function; `from __future__` not needed
  (3.10+). Frozen `@dataclass` for domain types (`ServiceRegistration`,
  `Finding`) — not dicts, not classes with behaviour.
- Pure functions for logic (rules, transforms); side effects (AWS calls,
  console output, cache) stay at the edges. Return results, don't mutate
  arguments.
- No ABCs, metaclasses, or deep class hierarchies unless two concrete
  implementations already demand them (rule 14).
- stdlib and existing dependencies first. A new runtime dependency is
  its own justified PR (what it buys, why stdlib can't).
- New modules mirror the existing layout: one service = one
  `services/<name>_service.py` + one registry entry; shared logic lives
  in `aws_scanner_lib`.
- Comments state constraints the code can't show — never narrate what
  the next line does.

## Documentation style

- README and all user-facing docs follow the **i-have-adhd** output
  style (`i-have-adhd@i-have-adhd` plugin skill): lead with the action,
  numbered steps with one bounded action each, no preamble, no closing
  filler, lists capped at 5. Use it both when generating docs and as the
  checklist when reviewing them.

## Testing

- The suite runs with **zero AWS credentials**: moto fakes AWS, conftest
  forces fake creds and redirects the pickle cache per-test.
- Tests are **characterization tests at seams** (public interfaces):
  scan_service/scan_region, the flattened resource-record shape, output
  formats, cache round-trips, each scanner against moto. Don't test
  internals; don't stub the dispatch mechanism.
- Waste rules (when built) are pure functions — test them with fixture
  dicts, no moto needed.
- CI (`.github/workflows/ci.yml`) is the merge gate; Codecov enforces
  80% patch coverage (project check tolerates 1% refactor wobble).

## Architecture notes

- Packages: `aws_scanner_lib` (orchestration, cache, outputs, clients,
  logging) and `services` (per-AWS-service scanners +
  `services/registry.py`, the single source of truth mapping service
  name → scanner + output processor).
- Adding a service = one module + one `SERVICES` registry entry.
- The flattened record contract (region/resource_type/resource_id/
  resource_arn, optional resource_name) is pinned by
  tests/test_resource_shape.py — changing it is a deliberate act.
- Refactor roadmap (C3 spec-driven scanner collapse → C4 typed Resource
  dataclass → C5 progress seam + logging shrink → C6 unified
  RegionScanner) is in flight — check open PRs and branches for current
  status rather than trusting this file.
- Product roadmap for the `waste` verb: `PRODUCT.md` §5.
