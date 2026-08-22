# Frontend: Next.js investigation console. Multi-stage build producing
# a minimal standalone runtime (see next.config.mjs's `output: "standalone"`).
#
# NOTE: no package-lock.json is committed (this project's sandbox had
# no npm registry access to generate one — see the root README). `npm
# install` below works without one, but isn't fully reproducible;
# running `npm install` once locally and committing the resulting
# package-lock.json is recommended before a real deployment, and this
# Dockerfile will automatically prefer `npm ci` once one exists.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

# Node has native fetch since v18 — no curl/wget dependency needed for
# a healthcheck in this alpine image.
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=10s \
  CMD node -e "fetch('http://localhost:3000').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
