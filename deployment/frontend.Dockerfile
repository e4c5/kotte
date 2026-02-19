FROM node:20-alpine

WORKDIR /app

# Copy frontend package files
COPY frontend/package.json frontend/package-lock.json* ./

# Install dependencies
RUN npm ci || npm install

# Copy frontend source
COPY frontend/ .

# Build arg for Vite proxy target (used at runtime for dev server)
ARG VITE_PROXY_TARGET=http://backend:8000
ENV VITE_PROXY_TARGET=${VITE_PROXY_TARGET}

EXPOSE 5173

CMD ["npm", "run", "dev"]
