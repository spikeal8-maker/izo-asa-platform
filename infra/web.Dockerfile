FROM node:24-bookworm-slim AS build
WORKDIR /build/apps/web
COPY apps/web/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY apps/web ./
COPY packages/contracts /build/packages/contracts
RUN npm run build
FROM caddy:2-alpine
COPY infra/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /build/apps/web/dist /srv
EXPOSE 8080
