# fima maintainer instructions

You are maintaining the fima Python package as a real production/open-source repository.

Your job is not only to edit code. You are responsible for the complete engineering workflow:
investigation -> GitHub issue -> branch -> implementation -> tests -> documentation -> PR -> CI -> review -> merge -> cleanup -> release preparation.

## Repository rules

- `master` is the stable/default branch.
- Never develop directly on `master`.
- Start each independent change from the latest `origin/master`.
- Use one focused GitHub Issue and one short-lived branch per logical change.
- Prefer branch names such as:
  - `fix/<issue>-description`
  - `feat/<issue>-description`
  - `refactor/<issue>-description`
- Do not mix unrelated modules or cleanup into a PR.
- Never force-push `master`.
- Never rewrite or move an existing release tag.
- Never use destructive Git commands unless clearly necessary and verified.
- Do not commit generated output files, credentials, local data, caches, build output, or unrelated files.
- Inspect `git status`, the staged diff, and the final PR diff before committing/pushing.

## Existing project workflow

The package has:
- deterministic/unit tests;
- separately marked live integration tests;
- GitHub Actions PR CI;
- a release workflow triggered by publication of a GitHub Release;
- packaging verification;
- fresh-wheel import verification;
- PyPI publishing through the release workflow.

Preserve this architecture unless there is a strong documented reason to change it.

## Testing philosophy

Every bug fix should first be reproduced or characterized.

For each change:

1. Understand the existing implementation and tests.
2. Reproduce the problem where possible.
3. Identify the root cause rather than patching symptoms.
4. Add or update deterministic tests that would fail without the fix.
5. Implement the smallest maintainable fix.
6. Run the relevant targeted tests.
7. Run the full non-integration suite.
8. Run appropriate integration tests when the external provider is reachable.
9. Run packaging/build verification when public package behavior is affected.

Do not make deterministic CI depend on third-party websites.

Live-provider tests must remain clearly separated from deterministic tests.

An external provider being down, blocking a CI IP, rate-limiting requests, or changing behavior is not automatically a bug in fima. Distinguish:
- fima implementation bugs;
- provider/API changes;
- transient provider outages;
- network/environment restrictions.

Do not hide real bugs by blindly skipping tests.

## External HTTP/provider code

When working with live finance-data providers:

- inspect the actual current provider behavior instead of guessing;
- check redirect chains, status codes, response format, required parameters, and error responses;
- do not silently replace an endpoint without evidence;
- prefer documented/stable endpoints when available;
- preserve HTTPS certificate verification unless there is a very specific justified reason not to;
- use finite timeouts;
- handle redirects appropriately;
- handle transient failures such as 429 and 5xx sensibly when retries are appropriate;
- avoid infinite retries;
- provide useful public exceptions/messages;
- never make network requests at module import time;
- keep provider-specific behavior isolated from the public API where practical;
- do not bypass access controls, CAPTCHAs, authentication, or provider restrictions.

If a provider cannot be reached from the Codex/CI environment but works elsewhere, document that distinction and design deterministic tests around mocked responses or legal fixtures instead of pretending the provider is working.

## Public API

Avoid unnecessary breaking changes.

For public functions:
- preserve documented signatures unless a change is necessary;
- document parameters, returns, and public exceptions;
- use meaningful exceptions rather than prints or silent empty results;
- maintain import compatibility through `fima/__init__.py` when appropriate.

## GitHub workflow

For a normal task:

1. Fetch the latest repository state.
2. Confirm local/current base against `origin/master`.
3. Create or update a focused GitHub Issue with:
   - problem;
   - reproduction/evidence;
   - expected behavior;
   - acceptance criteria.
4. Create a branch from the latest `origin/master`.
5. Implement in meaningful commits.
6. Push the branch.
7. Open a Draft PR early when useful.
8. Keep the PR description current.
9. Reference the issue.
10. When acceptance criteria are satisfied, use `Closes #<issue>`.
11. Inspect the complete PR diff for unrelated changes.
12. Run all required tests.
13. Make the PR Ready for Review.
14. Monitor CI.
15. Investigate and fix failures rather than bypassing them.
16. Review your own final diff as if you were an independent reviewer.
17. Address review feedback.
18. Only merge when the PR is complete and all required checks pass.
19. Prefer Squash and Merge for one cohesive feature/fix unless preserving individual commits is clearly useful.
20. After merge, verify `master`, the PR, the issue, and CI.
21. Clean up the feature branch safely.

If GitHub permissions or branch protection prevent an operation, do not work around the protection. Report exactly what human action is required.

## Releases

Treat releases separately from feature development.

Before a release:
- inspect the latest version actually published on PyPI;
- inspect Git tags and the version in `pyproject.toml`;
- determine the appropriate next version based on the project's versioning convention and the actual changes;
- never reuse or move an existing published tag;
- prepare the version change through a branch and PR;
- run tests and package verification;
- build the distribution;
- verify the wheel in a clean environment;
- verify public imports;
- verify forbidden/private files are absent.

The GitHub release tag and `pyproject.toml` package version must agree.

Never silently correct a tag/version mismatch. Fail and fix the release preparation.

Do not publish a GitHub Release / PyPI package until the user explicitly authorizes the final publication.

After authorization:
- tag the exact intended commit;
- create/publish the GitHub Release;
- monitor the release workflow;
- verify successful PyPI publication;
- report the published version, tag, commit, workflow result, and PyPI result.

## Definition of done

A task is not complete merely because code was edited.

It is complete only when:
- the root problem is understood;
- acceptance criteria are satisfied;
- tests pass;
- documentation is correct;
- the PR contains only intended changes;
- required CI is green;
- the GitHub workflow is complete;
- and the final repository state is verified.

Always finish with a concise report containing:
- root cause;
- files changed;
- tests executed and results;
- GitHub Issue;
- branch;
- commits;
- PR;
- CI status;
- merge status;
- remaining risks or external-provider limitations.