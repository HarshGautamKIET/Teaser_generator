# Build context is the REPOSITORY ROOT, not frontend/ -- vite.config.ts aliases
# @ds at ../design-system and sets envDir "..", so the design system must be
# inside the context. See the `context: .` on the frontend service in
# docker-compose.yml.
#
# Vite inlines VITE_* variables at build time, so they are build args rather
# than runtime env: the values are compiled into the bundle. Only the
# publishable Supabase key belongs here -- it is public by design. Never pass
# SUPABASE_SECRET_KEY into this stage.
FROM node:24-alpine AS build

ARG VITE_API_BASE_URL=http://127.0.0.1:8000/api
ARG VITE_SUPABASE_URL=http://localhost:8000
ARG VITE_SUPABASE_PUBLISHABLE_KEY

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_PUBLISHABLE_KEY=$VITE_SUPABASE_PUBLISHABLE_KEY

WORKDIR /repo

# Mirrors the repository layout so the ../design-system alias resolves.
COPY design-system ./design-system

WORKDIR /repo/frontend

# npm ci needs the lockfile; it also makes the install reproducible.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/tsconfig.json frontend/vite.config.ts frontend/index.html ./
COPY frontend/src ./src

RUN npm run build

FROM nginx:1.29-alpine
COPY --from=build /repo/frontend/dist /usr/share/nginx/html
# Single-page app: unknown paths must fall through to index.html, not 404.
RUN printf 'server {\n\
  listen 80;\n\
  root /usr/share/nginx/html;\n\
  location / { try_files $uri $uri/ /index.html; }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80

# busybox wget ships with the alpine image, so this costs nothing to add.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
