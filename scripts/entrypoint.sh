#!/bin/sh
set -e

# Ensure runtime directories exist inside the mounted data volume
mkdir -p /app/data/models

# Generate sample data on first run so the demo works out of the box
if [ ! -f /app/data/sample_transactions.csv ]; then
    echo "[transactiq] Generating sample transaction data..."
    python scripts/generate_mock_data.py
fi

exec "$@"
