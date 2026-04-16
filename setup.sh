#!/usr/bin/env bash
# Fresh-install setup for the NAS web server on Ubuntu.
# Wipes any previous checkout and re-provisions the runtime directories.

set -euo pipefail

echo "==> Removing previous /srv contents (requires sudo)"
sudo rm -rf /srv/

echo "==> Creating virtual environment"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing Python dependencies"
pip install -r requirements.txt

echo "==> Creating NAS storage directories"
sudo mkdir -p /srv/nas /srv/nas-backups
sudo chown "$USER:$USER" /srv/nas /srv/nas-backups

echo "==> Generating SECRET_KEY"
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
export SECRET_KEY

cat <<EOF

Setup complete.

To run the server in this shell:
  cd $REPO_DIR
  source .venv/bin/activate
  export SECRET_KEY='$SECRET_KEY'
  python3 app.py

To persist SECRET_KEY across sessions, append the export line to ~/.bashrc.
EOF
