FROM node:20-alpine

WORKDIR /app

# Copy frontend package files
COPY frontend/package.json frontend/package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ .

# Create non-root user
RUN addgroup -g 1000 -S nodejs && adduser -u 1000 -S nodejs -G nodejs \
    && chown -R nodejs:nodejs /app

ARG VITE_PROXY_TARGET=http://backend:8000
ENV VITE_PROXY_TARGET=${VITE_PROXY_TARGET}

USER nodejs

EXPOSE 5173
CMD ["npm", "run", "dev"]
