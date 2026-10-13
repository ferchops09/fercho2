FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src ./src
RUN npm run build


FROM node:22-alpine AS production

WORKDIR /app

RUN apk add --no-cache ffmpeg

COPY package*.json ./
RUN npm ci --only=production

COPY --from=builder /app/dist ./dist

RUN mkdir -p /app/auth_info_baileys /app/logs /app/shared

ENV NODE_ENV=production \
    DLAPI_URL=http://dlapi:7421

CMD ["node", "dist/index.js"]
