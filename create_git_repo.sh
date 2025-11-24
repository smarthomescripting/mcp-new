#!/bin/bash
# link_git_repo_force.sh
# Converts an HTTPS Git URL to SSH, initializes git in current directory,
# links origin, and FORCE PUSHES local contents to remote main branch.

echo "Enter the HTTPS URL of the Git repository (e.g. https://github.com/user/repo):"
read -r HTTPS_URL

if [[ -z "$HTTPS_URL" ]]; then
  echo "❌ No URL entered. Exiting."
  exit 1
fi

# Convert HTTPS → SSH
SSH_URL=$(echo "$HTTPS_URL" | sed -E 's#https://([^/]+)/([^/]+)/([^/]+)#git@\1:\2/\3.git#')

# Extract host (github.com, gitlab.com, etc.)
HOST=$(echo "$SSH_URL" | sed -E 's#git@([^:]+):.*#\1#')

echo "✅ Converted to SSH: $SSH_URL"
echo "🔍 Working directory: $(pwd)"

# Initialize repo if not yet a git repo
if [ ! -d ".git" ]; then
  git init
  echo "✅ Initialized new git repository in current directory."
else
  echo "ℹ️ Git repository already initialized."
fi

# Ensure main branch exists
if ! git show-ref --verify --quiet refs/heads/main; then
  git checkout -b main
fi

# Configure remote origin
if git remote | grep -q origin; then
  echo "⚠️ Remote 'origin' already exists. Updating it to $SSH_URL"
  git remote set-url origin "$SSH_URL"
else
  git remote add origin "$SSH_URL"
  echo "✅ Added remote origin: $SSH_URL"
fi

# Test SSH connection
echo "🔍 Checking SSH connection to $HOST ..."
ssh -T "git@$HOST" 2>/dev/null
if [[ $? -ne 1 && $? -ne 255 ]]; then
  echo "⚠️ SSH connection to $HOST failed. Ensure your SSH key is added (ssh-add ~/.ssh/id_rsa)."
else
  echo "✅ SSH authentication looks good."
fi

# Commit if no commits exist
if ! git rev-parse HEAD >/dev/null 2>&1; then
  echo "# $(basename "$(pwd)")" > README.md
  git add .
  git commit -m "Initial commit"
fi

# Force push local to remote
echo "🚀 Force pushing local main branch to remote..."
git branch -M main
git push -u origin main --force

if [[ $? -eq 0 ]]; then
  echo "✅ Successfully force-pushed local main branch to $SSH_URL"
else
  echo "❌ Force push failed. Check git logs or SSH settings."
fi
