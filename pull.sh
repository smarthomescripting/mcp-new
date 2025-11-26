#!/bin/bash

cd /home/mcp-new/ || exit 1

FORCE=false

# Parse parameters
while getopts "f" opt; do
  case $opt in
    f)
      FORCE=true
      ;;
    *)
      echo "Usage: $0 [-f]"
      exit 1
      ;;
  esac
done

if [ -f "pull.txt" ] || [ "$FORCE" = true ]; then
    if [ "$FORCE" = true ]; then
        echo "Force update triggered (-f)."
    else
        echo "pull.txt found. Running update..."
    fi

    # Pull latest changes
    /usr/bin/git pull

    # Restart Flask service
    /usr/bin/systemctl restart flask_app9

    # Optional: uncomment to check status
    # /usr/bin/systemctl status flask_app9

    # Remove pull.txt only if it existed
    if [ -f "pull.txt" ]; then
        rm -f pull.txt
        echo "pull.txt removed."
    fi

    echo "Update completed."
else
    echo "No pull.txt found and no force (-f) option given. Exiting."
fi
