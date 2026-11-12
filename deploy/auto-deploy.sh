#!/bin/bash
set -euo pipefail

cd /opt/bakecake

git fetch --quiet origin main

if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "$(date -Is) new commit $(git rev-parse --short origin/main), deploying"
  /opt/bakecake/deploy/deploy.sh
else
  echo "$(date -Is) up to date at $(git rev-parse --short HEAD), nothing to do"
fi
