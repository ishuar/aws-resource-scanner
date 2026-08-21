# CLAUDE.md

Python CLI that inventories AWS resources across regions/services (boto3,
typer, rich). Soon renamed to **aws-resource-inventory**.

## Non-negotiable engineering rules

1. **Best practice over workaround — always.** Fix the cause, not the
   symptom. If a tool's default is wrong for us, configure it explicitly
   and say why in a comment; never patch around it silently.
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
6. **Don't hand-roll what the platform provides.** botocore's adaptive
   retry mode owns transient-error retries (the old retry_with_backoff
   wrapper is deleted — do not reintroduce one). Same instinct applies to
   pagination (use paginators, always) and diffing.
7. **Unused features get deleted, not fixed.** `--compare`/deepdiff were
   removed after proving zero successful executions (the locked deepdiff
   couldn't even be imported). Apply the deletion test with evidence
   before investing in a fix.
8. **Every scanning client comes from
   `aws_scanner_lib.clients.get_scan_client`** — never `session.client()`
   directly. It owns pool size, timeouts, adaptive retries, the
   creation lock (boto3 sessions are not thread-safe for client
   creation), and the `aws-resource-inventory` user-agent stamp.
9. **Verify merges against real AWS**: `scripts/e2e-diff.sh` (no args)
   fetches origin and compares `origin/main~1` vs `origin/main` scan
   output. Run it after merging anything that touches scan behaviour;
   add `--tag-key/--tag-value` to cover the Resource Groups tag path.
10. **Squash merges + stacked PRs**: after a squash lands, rebase any
    dependent branch onto main (`git rebase --onto main <old-base>`).

## Testing

- The suite runs with **zero AWS credentials**: moto fakes AWS, conftest
  forces fake creds and redirects the pickle cache per-test.
- Tests are **characterization tests at seams** (public interfaces):
  scan_service/scan_region, the flattened resource-record shape, output
  formats, cache round-trips, each scanner against moto. Don't test
  internals; don't stub the dispatch mechanism.
- CI (`.github/workflows/ci.yml`) is the merge gate; Codecov enforces
  80% patch coverage (project check tolerates 1% refactor wobble).

## Architecture notes

- Entry point: `cli:app` (`aws-scanner`). Packages: `aws_scanner_lib`
  (orchestration, cache, outputs, clients, logging) and `services`
  (per-AWS-service scanners + `services/registry.py`, the single source
  of truth mapping service name → scanner + output processor).
- Adding a service = one module + one `SERVICES` registry entry.
- The flattened record contract (region/resource_type/resource_id/
  resource_arn, optional resource_name) is pinned by
  tests/test_resource_shape.py — changing it is a deliberate act.
- Active roadmap (agreed via grilling, tracked in session memory):
  C3 spec-driven scanner collapse → C4 typed Resource dataclass (+ name
  backfill) → C5 progress seam then logging shrink (+ CLI tests) →
  C6 unified RegionScanner over the per-service and tag scan paths.
- Queued chore: curated ruff rule-set expansion (E/W/F/I/B/UP/SIM/DTZ/RUF
  with justified ignores), fixing all findings in one reviewed PR.
