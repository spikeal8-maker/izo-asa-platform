FROM node:24-bookworm-slim AS build
WORKDIR /build/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web ./
COPY packages/contracts /build/packages/contracts
RUN npm run build
FROM caddy:2-alpine
COPY infra/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /build/apps/web/dist /srv
EXPOSE 8080
