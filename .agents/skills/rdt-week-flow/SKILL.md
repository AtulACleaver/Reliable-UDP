---
name: rdt-week-flow
description: Runs the weekly GitHub cycle on the CS30003 RDT project: opening Issues from the week plan, cutting a branch, committing against the Issue, opening the pull request, merging to main and closing the Issue. Use at the start of a week, when starting a task, and when a task is ready to ship.
---

# The weekly cycle

Every week runs the same five steps. Never skip one, never reorder them.

## Step 1: Issues, at the start of the week

First, export that week's Notion pages to docs/plan/week-N*.md and commit them
as "docs(plan): week N". The committed file, not the Notion page, is what every
agent reads for the rest of the week.

Then one Issue per deliverable in that week's plan table. Each Issue has:

- Title: the deliverable, not the activity. "GBN window slides on cumulative
  ACK", not "work on GBN".
- Body: the proof line from the plan, the exact command that must pass, and the
  contracts it depends on.
- Label lane1 .. lane5, assignee is the lane owner, milestone is the week.

If a deliverable cannot be stated as a command that either passes or fails, it
is not ready to be an Issue. Say so instead of opening it.

## Step 2: one branch per Issue, cut from main

```bash
git checkout main && git pull
git checkout -b lane2/17-gbn-window-slide
```

Branch name is lane<N>/<issue-number>-<slug>. Always from an up-to-date main.
Never branch from another branch.

## Step 3: commit against the Issue

Small commits, conventional prefix, lane scope, imperative summary under 70
characters, with "refs #17" in the body. One concern per commit. Aim for one
commit a day; the graded bar is two per person per week.

```bash
git commit -m "feat(gbn): slide base on cumulative ack" -m "refs #17"
git push -u origin lane2/17-gbn-window-slide
```

## Step 4: the pull request

Open it as soon as there is something reviewable, as a draft if needed. Do not
wait for the branch to be finished.

Title: same as the Issue.
Body: the PR template, plus "Closes #17" so the merge closes the Issue.
CODEOWNERS auto-requests the reviewer. Do not pick one manually.

Before marking it ready, run exactly what CI runs: `make check`, then
`python tasks.py smoke`. Both green.

If the branch is more than two days old, rebase onto main before review.

## Step 5: merge, close, repeat

One approving review plus green CI. Rebase and merge so history stays linear
and git bisect keeps working. The merge closes the Issue. Delete the branch.

## End of week

When every Issue in the milestone is closed and the exit-gate command passes on
a clean clone, tag it and close the milestone:

```bash
git tag week1-gate && git push --tags
```

That tag is the week's checkpoint and the commit the report and the results CSV
point at.

## When asked to start work

Ask for the Issue number first. If there is no Issue, open one (Step 1) before
cutting a branch. Never begin implementation on main or on an unnamed branch.
