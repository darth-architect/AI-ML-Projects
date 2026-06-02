#!/usr/bin/env bash
# push_all.sh
# Pushes each project to its corresponding branch in darth-architect/AI-ML-Projects
#
# Usage:
#   chmod +x push_all.sh
#   ./push_all.sh
#
# Prerequisites:
#   - git installed and authenticated (SSH key or HTTPS token)
#   - Run this script from the directory containing all three project folders:
#       beacon-rag/
#       sailor-rec/
#       kys-mcp/

set -euo pipefail

REPO="https://github.com/darth-architect/AI-ML-Projects.git"
# Or use SSH: git@github.com:darth-architect/AI-ML-Projects.git

declare -A PROJECTS=(
  ["beacon-rag"]="RAG-Foundations"
  ["sailor-rec"]="LangGraph-Agents"
  ["kys-mcp"]="MCP-Projects"
)

for PROJECT_DIR in "${!PROJECTS[@]}"; do
  BRANCH="${PROJECTS[$PROJECT_DIR]}"

  echo ""
  echo "========================================="
  echo "  Project : $PROJECT_DIR"
  echo "  Branch  : $BRANCH"
  echo "========================================="

  if [ ! -d "$PROJECT_DIR" ]; then
    echo "  ⚠️  Directory '$PROJECT_DIR' not found — skipping."
    continue
  fi

  # Create a temp clone of the repo, checkout the branch, copy files, push
  TMPDIR=$(mktemp -d)
  echo "  Cloning repo into $TMPDIR..."
  git clone --quiet "$REPO" "$TMPDIR"

  cd "$TMPDIR"
  git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"

  echo "  Copying files from $PROJECT_DIR/..."
  cp -r "$OLDPWD/$PROJECT_DIR/." .

  git add -A

  if git diff --cached --quiet; then
    echo "  Nothing to commit for $BRANCH."
  else
    git commit -m "feat: initial commit — $PROJECT_DIR"
    git push origin "$BRANCH"
    echo "  ✅ Pushed $PROJECT_DIR → $BRANCH"
  fi

  cd "$OLDPWD"
  rm -rf "$TMPDIR"
done

echo ""
echo "All done."
