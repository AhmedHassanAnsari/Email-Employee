# syntax=docker/dockerfile:1

# ---- deps ----
# Install dependencies against the lockfile so this layer only busts when deps change.
FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci


# ---- builder ----
# Compile the Vite/React app into static assets.
FROM node:20-alpine AS builder

ENV NODE_ENV=production

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# API base is baked into the bundle at build time (Vite inlines import.meta.env).
ARG VITE_API_BASE=http://localhost:8001
ENV VITE_API_BASE=${VITE_API_BASE}

RUN npm run build


# ---- runtime ----
# Serve the static bundle with nginx. No node/build tooling ships in the final image.
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

# Run nginx as the unprivileged 'nginx' user on an unprivileged port.
RUN touch /var/run/nginx.pid \
    && chown -R nginx:nginx /var/run/nginx.pid /var/cache/nginx /usr/share/nginx/html

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
