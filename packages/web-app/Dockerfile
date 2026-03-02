# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests first for better layer caching
COPY package*.json ./

# Install dependencies (clean install for reproducible builds)
RUN npm ci

# Copy source files
COPY . .

# Build the Vite + React + TypeScript app (tsc -b && vite build)
RUN npm run build

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM nginx:alpine AS runtime

LABEL maintainer="SignalOps Team"
LABEL description="SignalOps Web App — React/Vite SPA served via nginx with API proxy"

# Copy the compiled SPA assets from the builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Replace the default nginx config with our SPA + API proxy config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000 || exit 1

CMD ["nginx", "-g", "daemon off;"]
