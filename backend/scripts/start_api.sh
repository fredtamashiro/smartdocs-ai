#!/bin/sh
set -e

# OpenTelemetry reads this before the Langfuse client creates its tracer provider.
export OTEL_SERVICE_NAME="${OTEL_SERVICE_NAME:-smartdocs-backend}"

uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
