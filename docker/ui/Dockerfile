FROM node:22-alpine AS build

WORKDIR /app

COPY ./ui/package.json ./package.json
COPY ./ui/package-lock.json* ./
RUN npm install

COPY ./ui/README.md ./README.md
COPY ./ui/index.html ./index.html
COPY ./ui/vite.config.js ./vite.config.js
COPY ./ui/generate-build-version.js ./generate-build-version.js
COPY ./ui/public ./public
COPY ./ui/src ./src
COPY ./LICENSE ./LICENSE

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/build /var/www
COPY ./ui/nginx.conf /etc/nginx/nginx.conf
COPY ./LICENSE /app/LICENSE
EXPOSE 80

ENTRYPOINT ["nginx", "-g", "daemon off;"]
