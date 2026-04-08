# ── Build frontend ────────────────────────────────────────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /app
RUN npm install -g pnpm
COPY services/frontend/package.json services/frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY services/frontend/ .
RUN pnpm build

# ── Production nginx ──────────────────────────────────────────────────────────
FROM nginx:1.27-alpine
COPY infrastructure/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend-build /app/dist /usr/share/nginx/html
