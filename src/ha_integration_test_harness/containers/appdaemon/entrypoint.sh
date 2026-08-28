#!/usr/bin/env sh
set -e

echo "⏳ Initializing AppDaemon..."

echo "⏳ Waiting for Home Assistant token..."

# Wait for the token file to be created
max_attempts=60
attempt=0
while [ $attempt -lt $max_attempts ]; do
  if [ -f /shared_data/.ha_token ]; then
    echo "✅ Token file found"
    break
  fi
  attempt=$((attempt + 1))
  sleep 1
done

if [ $attempt -eq $max_attempts ]; then
  echo "❌ Token file not found after 60 seconds"
  exit 1
fi

# Read the token
TOKEN=$(cat /shared_data/.ha_token)

if [ -z "$TOKEN" ]; then
  echo "❌ Token file is empty"
  exit 1
fi

echo "🔑 Configuring AppDaemon with token"

# Update the appdaemon.yaml with the actual token
sed "s|token: .*|token: ${TOKEN}|" /conf/appdaemon.yaml.template > /conf/appdaemon.yaml

echo "✅ AppDaemon configured"
echo "   Token: ${TOKEN}"

# Start AppDaemon in the background and monitor its logs
appdaemon -c /conf > /tmp/appdaemon.log 2>&1 &
APPDAEMON_PID=$!

# Wait for AppDaemon to fully initialize
echo "⏳ Waiting for AppDaemon to initialize..."
if timeout 60 sh -c '
  while ! grep -q "AppDaemon: All plugins ready" /tmp/appdaemon.log && \
        ! grep -q "HASS: Completed initialization" /tmp/appdaemon.log && \
        ! grep -q "AppDaemon: Calling initialize()" /tmp/appdaemon.log; do
    sleep 1
  done
'; then
  echo "✅ AppDaemon fully initialized"
  touch /shared_data/.appdaemon_ready
else
  echo "❌ AppDaemon failed to initialize within 60 seconds"
  exit 1
fi

# Keep the process running
wait $APPDAEMON_PID
