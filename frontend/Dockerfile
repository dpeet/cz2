# ==============================================================================
# Mountain House Thermostat - Frontend (mountainstat-main) Dockerfile
# ==============================================================================
# Multi-stage build: Vite build stage + Nginx serving stage
# Produces lightweight production image with static React SPA
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build React application with Vite
# ------------------------------------------------------------------------------
FROM node:24-alpine AS builder

WORKDIR /app

# Copy dependency manifests for layer caching
COPY package.json package-lock.json ./

# Install production + dev dependencies (needed for build)
RUN npm ci

# Copy application source
COPY . .

# Build arguments for environment variables (passed at build time)
# No defaults - must be provided by docker-compose or build command
ARG VITE_API_BASE_URL
ARG VITE_API_TIMEOUT_MS
ARG VITE_MQTT_WS_URL

# Inject build-time env vars (Vite embeds these into bundle)
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_API_TIMEOUT_MS=${VITE_API_TIMEOUT_MS}
ENV VITE_MQTT_WS_URL=${VITE_MQTT_WS_URL}

# Ensure local dev overrides are NOT used in production build
RUN rm -f .env.local || true

# Build production bundle (outputs to dist/)
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Serve static files with Nginx
# ------------------------------------------------------------------------------
FROM nginx:alpine

# Copy custom nginx config with SPA fallback support
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Generate runtime config.js from environment when container starts
ENV RUNTIME_VITE_API_BASE_URL=""
ENV RUNTIME_VITE_API_TIMEOUT_MS=""
ENV RUNTIME_VITE_MQTT_WS_URL=""

RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -e' \
    '' \
    '# Read build hash generated during Vite build' \
    'BUILD_HASH=$(cat /usr/share/nginx/html/.build-hash 2>/dev/null || echo "unknown")' \
    '' \
    '# Generate runtime config from environment variables' \
    'cat > /usr/share/nginx/html/config.js <<EOF' \
    'window.__MOUNTAINSTAT_CONFIG__ = {' \
    "  VITE_API_BASE_URL: \"\${RUNTIME_VITE_API_BASE_URL}\"," \
    "  VITE_API_TIMEOUT_MS: \"\${RUNTIME_VITE_API_TIMEOUT_MS}\"," \
    "  VITE_MQTT_WS_URL: \"\${RUNTIME_VITE_MQTT_WS_URL}\"" \
    '};' \
    'EOF' \
    '' \
    'echo "Runtime config generated with hash: \${BUILD_HASH}"' \
    '' \
    'exec nginx -g "daemon off;"' > /docker-entrypoint.sh && \
    chmod +x /docker-entrypoint.sh

# Expose HTTP port (internal to compose network)
EXPOSE 80

# Health check for container orchestration (uses nginx /health endpoint)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD test -f /usr/share/nginx/html/index.html || exit 1

# Start nginx (foreground mode)
CMD ["/docker-entrypoint.sh"]

# ==============================================================================
# Build Instructions:
# - Default:  docker build -t mountainstat-frontend .
# - Custom:   docker build --build-arg VITE_API_BASE_URL=http://api:8000 \
#             -t mountainstat-frontend .
# ==============================================================================
