# GitHub Commit Guide — Member 2 Backend Contribution

This guide walks you through committing and pushing the backend code to the shared hackathon repository.

## Prerequisites

- Git is installed (`git --version`).
- You have access to the shared repository.
- You are working inside the `api-hallucination-firewall/` project directory.

---

## Step 1 — Inspect the Repository

Before making any changes, check the current state:

```bash
# Check if a Git repository exists
git status

# See the current branch
git branch --show-current

# Check remote(s)
git remote -v

# View recent commits
git log --oneline -5
```

If no repository exists yet:

```bash
git init
git remote add origin https://github.com/<your-org>/api-hallucination-firewall.git
```

> **Warning:** If the repository is already initialized by a teammate, do NOT run `git init` again.

---

## Step 2 — Create the Backend Feature Branch

```bash
# Make sure you are on the main branch first
git checkout main
git pull origin main

# Create and switch to the backend feature branch
git checkout -b feature/backend
```

If the branch already exists:

```bash
git checkout feature/backend
git pull origin feature/backend
```

---

## Step 3 — Review Modified Files

Before staging, inspect what has changed:

```bash
# See all modified, added, and untracked files
git status

# View the diff for modified files
git diff
```

> **Important:** Only stage files within the `backend/` directory. Do not stage teammates' unfinished frontend or Gemma files.

---

## Step 4 — Stage and Commit in Logical Steps

### Commit 1 — Initialize Backend Project

```bash
git add backend/requirements.txt
git add backend/.gitignore
git add backend/.env.example
git add backend/pytest.ini
git add backend/app/__init__.py
git add backend/app/config.py
```

Review staged changes:

```bash
git diff --cached
```

Commit:

```bash
git commit -m "chore(backend): initialize Python backend project"
```

---

### Commit 2 — Add API Schemas

```bash
git add backend/app/schemas.py
```

```bash
git diff --cached
git commit -m "feat(backend): define verification API request and response schemas"
```

---

### Commit 3 — Implement Python AST Parser

```bash
git add backend/app/parser.py
```

```bash
git diff --cached
git commit -m "feat(parser): extract imports, calls, and keyword arguments from Python AST"
```

---

### Commit 4 — Add Versioned API Reference Data

```bash
git add backend/data/requests/2.31.0.json
git add backend/app/knowledge_base.py
```

```bash
git diff --cached
git commit -m "feat(data): add versioned requests 2.31.0 API reference snapshot"
```

---

### Commit 5 — Implement Suggestion Engine

```bash
git add backend/app/suggestions.py
```

```bash
git diff --cached
git commit -m "feat(suggestions): add deterministic keyword and symbol suggestion engine"
```

---

### Commit 6 — Implement Deterministic Verification Engine

```bash
git add backend/app/verifier.py
```

```bash
git diff --cached
git commit -m "feat(verifier): validate API usage against trusted reference data"
```

---

### Commit 7 — Add FastAPI Endpoints

```bash
git add backend/app/main.py
```

```bash
git diff --cached
git commit -m "feat(api): expose health check and verification endpoints"
```

---

### Commit 8 — Add Automated Tests

```bash
git add backend/tests/__init__.py
git add backend/tests/test_health.py
git add backend/tests/test_parser.py
git add backend/tests/test_knowledge_base.py
git add backend/tests/test_verifier.py
git add backend/tests/test_api.py
git add backend/tests/test_edge_cases.py
```

```bash
git diff --cached
git commit -m "test(backend): add 89 tests covering parser, verifier, API, and edge cases"
```

---

### Commit 9 — Add Documentation

```bash
git add backend/README.md
git add backend/GITHUB_COMMIT_GUIDE.md
git add backend/TECHNICAL_DOCUMENTATION.md
```

```bash
git diff --cached
git commit -m "docs(backend): add README, technical docs, and GitHub commit guide"
```

---

## Step 5 — Verify Before Pushing

```bash
# Check that all commits are on your branch
git log --oneline -10

# Confirm you are on the right branch
git branch --show-current

# Make sure no untracked backend files are left unstaged
git status
```

---

## Step 6 — Push to Remote

```bash
git push -u origin feature/backend
```

If the branch already exists on the remote:

```bash
git push origin feature/backend
```

---

## Step 7 — Open a Pull Request

1. Go to the GitHub repository page.
2. Click **"Compare & pull request"** for the `feature/backend` branch.
3. Title: `feat(backend): Add API Hallucination Firewall verification backend`
4. Description: Briefly explain what the backend does and list the key files.
5. Request review from your teammates.
6. Do **not** merge without review.

---

## Important Reminders

### What NOT to commit

| Item | Why |
|---|---|
| `.venv/` | Virtual environments are local |
| `.env` | May contain secrets |
| `__pycache__/` | Python bytecode is generated |
| `.pytest_cache/` | Test cache is temporary |

The `.gitignore` already excludes these.

### What NOT to do

- **Do not** run `git add .` blindly — it may stage teammates' files.
- **Do not** run `git reset --hard` unless you understand you will lose changes.
- **Do not** run `git push --force` on shared branches.
- **Do not** modify the remote URL without team agreement.
- **Do not** commit directly to `main` if the team uses pull requests.

### Key Git Concepts

- `git add` **stages** files but does NOT create a commit.
- `git commit` **records** staged changes locally.
- `git push` **uploads** local commits to the remote repository.
- `git status` shows what is staged, modified, and untracked.
- `git diff` shows unstaged changes; `git diff --cached` shows staged changes.

---

## Pre-Push Checklist

- [ ] All commits are on `feature/backend`, not `main`.
- [ ] Only `backend/` files are staged and committed.
- [ ] `.env`, `.venv/`, and `__pycache__/` are excluded.
- [ ] Tests pass: `python -m pytest tests/ -v`.
- [ ] No secrets or credentials are committed.
- [ ] The server starts: `uvicorn app.main:app --reload`.
- [ ] `git log --oneline` shows logical, incremental commits.
- [ ] `git status` is clean (no unstaged backend files).

---

## Common Issues

### "fatal: not a git repository"

You are not inside a Git repository. Navigate to the project root or run `git init`.

### "error: failed to push some refs"

The remote branch has new commits. Pull first:

```bash
git pull --rebase origin feature/backend
```

### "Permission denied"

You may not have push access. Ask the repository owner to add you as a collaborator.

### Accidentally staged wrong files

```bash
git reset HEAD <file>   # Unstage a specific file
```
