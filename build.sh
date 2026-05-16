#!/bin/bash
set -e
pip install -r requirements.txt
mkdir -p ephe
curl -fsSL \
  "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/sefstars.txt" \
  -o ephe/sefstars.txt
echo "sefstars.txt downloaded successfully"
