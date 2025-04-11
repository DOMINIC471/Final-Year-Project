#!/bin/bash

# -------------------------------------
# CONFIGURATION (CLI args or ENV fallback)
# -------------------------------------
DB="${1:-$ACTIVE_DB}"
RATE_LABEL="${2:-${RATE_LABEL:-100mpm}}"
INTERVAL=5
DURATION=300
DATESTAMP=$(date -u +"%Y%m%dT%H%M%S")

# Determine container name
case "$DB" in
  baseline) CONTAINER_NAME="baseline_sql" ;;
  timescaledb) CONTAINER_NAME="timescaledb" ;;
  influxdb) CONTAINER_NAME="influxdb-master" ;;
  victoriametrics) CONTAINER_NAME="victoria-metrics" ;;
  *) echo "❌ Unknown database: $DB" && exit 1 ;;
esac

# -------------------------------------
# LOG SETUP
# -------------------------------------
LOG_DIR="logs/global/$DB"
mkdir -p "$LOG_DIR"
OUTPUT_FILE="$LOG_DIR/global_resource_log_${RATE_LABEL}_${DB}_${DATESTAMP}.csv"
echo "Timestamp,CPU%,RSS_KB" > "$OUTPUT_FILE"

echo "⏱️ Monitoring PID 1 inside $CONTAINER_NAME"
echo "📝 Logging every $INTERVAL seconds for $((DURATION / INTERVAL)) samples..."
echo "📁 Output file: $OUTPUT_FILE"
echo "-----------------------------"

# -------------------------------------
# Detect if container uses BusyBox
# -------------------------------------
IS_BUSYBOX=$(docker exec "$CONTAINER_NAME" sh -c "ps --version 2>&1 | grep -i busybox")

if [[ -n "$IS_BUSYBOX" ]]; then
  echo "🔍 Detected BusyBox-based container — using 'top' for both CPU and RSS"
else
  echo "✅ Standard 'ps' available — using 'ps' for metrics"
fi

# -------------------------------------
# WAIT FOR PID 1 TO APPEAR
# -------------------------------------
MAX_WAIT=30
WAITED=0
while true; do
  LINE=$(docker exec "$CONTAINER_NAME" sh -c "ps | grep '^ *1 '")
  if [[ -n "$LINE" ]]; then
    echo "✅ PID 1 detected in $CONTAINER_NAME"
    break
  fi
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "❌ PID 1 not found after $MAX_WAIT seconds."
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ"),ERROR,PID_NOT_FOUND" >> "$OUTPUT_FILE"
    exit 1
  fi
  echo "⏳ Waiting for PID 1 to appear..."
  sleep 1
  WAITED=$((WAITED + 1))
done

# -------------------------------------
# MONITOR LOOP
# -------------------------------------
for ((i = 0; i < DURATION; i += INTERVAL)); do
  TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  if [[ -n "$IS_BUSYBOX" ]]; then
    # BusyBox containers → top for both metrics
    LINE=$(docker exec "$CONTAINER_NAME" sh -c "top -b -n 1 | grep '^ *1 '")
    CPU=$(echo "$LINE" | awk '{print $9}' | tr -d '%')
    VSZ_MB=$(echo "$LINE" | awk '{print $5}' | sed 's/m//' )
    RSS_KB=$(awk "BEGIN {printf \"%.0f\", $VSZ_MB * 1024}")
  else
    # Normal Debian/Ubuntu containers → ps
    STATS=$(docker exec "$CONTAINER_NAME" ps -p 1 -o %cpu=,rss= 2>/dev/null)
    CPU=$(echo "$STATS" | awk '{print $1}')
    RSS_KB=$(echo "$STATS" | awk '{print $2}')
  fi

  if [[ "$CPU" =~ ^[0-9.]+$ && "$RSS_KB" =~ ^[0-9]+$ ]]; then
    echo "$TIMESTAMP,$CPU,$RSS_KB" >> "$OUTPUT_FILE"
  else
    echo "$TIMESTAMP,ERROR,ERROR" >> "$OUTPUT_FILE"
  fi

  sleep "$INTERVAL"
done

echo "✅ Monitoring complete: $OUTPUT_FILE"
