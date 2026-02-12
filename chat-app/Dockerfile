# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Set build-time environment variables
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_GEMINI_API_KEY
ARG VITE_MODEL=gemini-3-flash-preview

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_GEMINI_API_KEY=$VITE_GEMINI_API_KEY
ENV VITE_MODEL=$VITE_MODEL

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
