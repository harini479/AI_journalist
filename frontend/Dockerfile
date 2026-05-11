# ============================================
# AI Journalist — Frontend (React + Vite)
# Multi-stage: Build with Node → Serve with 'serve'
# ============================================

# --- Stage 1: Build ---
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies (cached layer)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# --- Stage 2: Serve ---
FROM node:20-alpine

RUN npm install -g serve

COPY --from=builder /app/dist /app/dist

EXPOSE 9110

CMD ["serve", "-s", "/app/dist", "-l", "9110"]
