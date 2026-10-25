#!/usr/bin/env bash
set -e

echo "⏳ Initializing Home Assistant..."

# Every startup wait below shares this budget. Keep it below the compose healthcheck's budget
# (start_period + retries * interval in docker-compose.yaml), or the container is marked
# unhealthy before this script can report why it timed out.
STARTUP_TIMEOUT=120
STARTUP_DEADLINE=$((SECONDS + STARTUP_TIMEOUT))

print_diagnostics() {
  echo "📋 Container diagnostics:"
  if pgrep hass >/dev/null 2>&1; then
    echo "   HA process: running (PID: $(pgrep hass))"
  else
    echo "   HA process: not running"
  fi
  if [[ -f /config/home-assistant.log ]]; then
    echo "   Last 20 lines of HA log:"
    tail -n 20 /config/home-assistant.log
  fi
}

# Poll a command once a second until it succeeds, or exit once the shared startup deadline passes.
# Usage: wait_until <description> <command> [args...]
wait_until() {
  local description="$1"
  shift
  echo "⏳ Waiting for ${description}..."
  while (( SECONDS < STARTUP_DEADLINE )); do
    if "$@"; then
      echo "✅ Done waiting for ${description}"
      return 0
    fi
    sleep 1
  done
  echo "❌ Timed out waiting for ${description} (startup budget: ${STARTUP_TIMEOUT}s)"
  print_diagnostics
  exit 1
}

ha_api_responding() {
  curl -s --max-time 2 http://localhost:8123/api/ > /dev/null 2>&1
}

# The API answers before startup completes; RUNNING means all integrations, including automations, are set up.
ha_running() {
  curl -s --max-time 2 http://localhost:8123/api/config -H "Authorization: Bearer ${ACCESS_TOKEN}" | grep -q '"state": *"RUNNING"'
}

# Ensure essential config files, which are not version controlled, exist
touch /config/automations.yaml

# Clean any existing .storage directory to ensure fresh state
# This prevents "User step already done" errors in CI
rm -rf /config/.storage
mkdir -p /config/.storage

# Start Home Assistant in the background via the wrapper (patches time.time() before HA loads)
echo "🚀 Starting Home Assistant..."
python /hass_wrapper.py --config /config &
HA_PID=$!

wait_until "the Home Assistant API to respond" ha_api_responding

# Create a test user via the onboarding API
echo "👤 Creating test user..."
CREATE_USER_RESPONSE=$(curl -s -X POST http://localhost:8123/api/onboarding/users \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "http://localhost",
    "name": "Test User",
    "username": "test_user",
    "password": "test_password",
    "language": "en"
  }')

# Extract the auth code from the response
AUTH_CODE=$(echo "$CREATE_USER_RESPONSE" | grep -o '"auth_code":"[^"]*"' | cut -d'"' -f4)

if [ -z "$AUTH_CODE" ]; then
  echo "❌ Failed to create user or extract auth code"
  echo "Response: $CREATE_USER_RESPONSE"
  exit 1
fi

# Exchange auth code for tokens
echo "🔑 Exchanging auth code for tokens..."
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8123/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&code=${AUTH_CODE}&client_id=http://localhost")

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$ACCESS_TOKEN" ]; then
  echo "❌ Failed to get access token"
  echo "Response: $TOKEN_RESPONSE"
  exit 1
fi

# Generate a long-lived access token for integration tests
# This prevents token expiration when tests manipulate time
bash /generate_long_lived_token.sh "$ACCESS_TOKEN"

echo "✅ Test user configured successfully"
echo "   Username: test_user"
echo "   Password: test_password"

echo "📋 Completing onboarding steps..."

# Complete core_config step
CORE_CONFIG_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8123/api/onboarding/core_config \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

if [[ "$CORE_CONFIG_STATUS" != 2* ]]; then
  echo "❌ Failed to complete core_config onboarding step (status: ${CORE_CONFIG_STATUS})"
  exit 1
fi

# Complete analytics step
ANALYTICS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8123/api/onboarding/analytics \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

if [[ "$ANALYTICS_STATUS" != 2* ]]; then
  echo "❌ Failed to complete analytics onboarding step (status: ${ANALYTICS_STATUS})"
  exit 1
fi

# Complete integration step
INTEGRATION_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8123/api/onboarding/integration \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "http://localhost:8123/",
    "redirect_uri": "http://localhost:8123/?auth_callback=1"
  }')

if [[ "$INTEGRATION_STATUS" != 2* ]]; then
  echo "❌ Failed to complete integration onboarding step (status: ${INTEGRATION_STATUS})"
  exit 1
fi
echo "✅ Onboarding steps completed"

wait_until "Home Assistant startup to complete (RUNNING state)" ha_running

# Create readiness marker to signal initialization is complete
touch /shared_data/.homeassistant_ready

# Keep Home Assistant running in foreground
echo "✅ Home Assistant initialization complete"
wait $HA_PID
