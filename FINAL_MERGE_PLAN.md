# Merge Plan

## Current Situation
- origin/main: clean upstream (already merged feat/react-frontend via PR #2)
- local main: behind origin/main by ~46 files (missing frontend, demo notebook, etc.)
- final-integrated-2026-03-29: the clean final branch with all improvements

## Recommended Steps

```bash
# 1. Ensure final branch has all changes committed
git checkout final-integrated-2026-03-29
git status  # should be clean

# 2. Update local main to match upstream
git checkout main
git pull origin main

# 3. Merge the final branch into main
git merge final-integrated-2026-03-29

# 4. Push to remote
git push origin main
```

## Alternative: Fast-forward (if main is a direct ancestor)
```bash
git checkout main
git pull origin main
git merge --ff-only final-integrated-2026-03-29
git push origin main
```

## Safety Notes
- Do NOT push local main as-is until reconciled with origin/main
- Use final-integrated-2026-03-29 as the source of truth
- origin/main already has the feat/react-frontend merge (PR #2), so the final branch is a superset
- The final branch adds: /verify primary flow improvements, frontend mode indicators, .gitignore cleanup, documentation
