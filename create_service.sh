#!/bin/bash

# Directory containing the service files
SERVICE_DIR="/etc/systemd/system"

# Find the highest-numbered flask_appN.service
last_file=$(ls "$SERVICE_DIR"/flask_app*.service 2>/dev/null | sort -V | tail -n 1)

if [[ -z "$last_file" ]]; then
    # If none found, start with flask_app1.service
    new_number=1
else
    # Extract the last number and increment
    last_number=$(basename "$last_file" | grep -oE '[0-9]+' | tail -n 1)
    new_number=$((last_number + 1))
fi

new_file="$SERVICE_DIR/flask_app${new_number}.service"

# Detect current working directory name
current_dir=$(basename "$(pwd)")

# Calculate port = 5000 + new_number
port=$((5000 + new_number))

echo "Creating new service: $new_file"
echo "Assigned port: $port"

# Create the systemd service file
cat > "$new_file" <<EOF
[Unit]
Description=Gunicorn instance to serve Flask app
After=network.target

[Service]
#User=your_user
#Group=www-data
WorkingDirectory=/home/${current_dir}/
Environment="PATH=/home/${current_dir}/tenv/bin"
ExecStart=/home/${current_dir}/.venv/bin/uvicorn app:app --host 127.0.0.1 --port ${port} --workers 4

[Install]
WantedBy=multi-user.target
EOF

# Set permissions and reload systemd
chmod 644 "$new_file"
systemctl daemon-reload

echo "✅ Created $new_file and reloaded systemd (port ${port})."

# Create pull.sh in the current directory
pull_script="/home/${current_dir}/pull.sh"

cat > "$pull_script" <<EOF
#!/bin/bash

cd /home/${current_dir}/ || exit 1

FORCE=false

# Parse parameters
while getopts "f" opt; do
  case \$opt in
    f)
      FORCE=true
      ;;
    *)
      echo "Usage: \$0 [-f]"
      exit 1
      ;;
  esac
done

if [ -f "pull.txt" ] || [ "\$FORCE" = true ]; then
    if [ "\$FORCE" = true ]; then
        echo "Force update triggered (-f)."
    else
        echo "pull.txt found. Running update..."
    fi

    # Pull latest changes
    /usr/bin/git pull

    # Restart Flask service
    /usr/bin/systemctl restart flask_app${new_number}

    # Optional: uncomment to check status
    # /usr/bin/systemctl status flask_app${new_number}

    # Remove pull.txt only if it existed
    if [ -f "pull.txt" ]; then
        rm -f pull.txt
        echo "pull.txt removed."
    fi

    echo "Update completed."
else
    echo "No pull.txt found and no force (-f) option given. Exiting."
fi
EOF

chmod +x "$pull_script"
echo "✅ Created $pull_script (linked to flask_app${new_number})"
