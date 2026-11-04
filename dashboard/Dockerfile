FROM node:24-bookworm-slim AS build
WORKDIR /frontend
COPY dashboard/package*.json ./
RUN npm ci
COPY dashboard/ ./
COPY extensions/vscode/src/contracts.ts /extensions/vscode/src/contracts.ts
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /frontend/dist /usr/share/nginx/html
COPY dashboard/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
