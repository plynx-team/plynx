FROM node:16-alpine

# Set the working directory to /app
WORKDIR /app

# Copy files
ADD ./ui/README.md                  /app
ADD ./ui/generate-build-version.js  /app
ADD ./ui/package-lock.json          /app
ADD ./ui/package.json               /app
ADD ./ui/public                     /app/public
ADD ./ui/src                        /app/src

# Copy licence
ADD ./LICENSE /app

# Build
ENV NODE_OPTIONS "--max-old-space-size=8192"
RUN npm install
RUN npm run build


# Use second stage nginx image
FROM nginx:1.17-alpine

COPY --from=0 /app/build /var/www
ADD ./ui/nginx.conf /etc/nginx/nginx.conf
ADD ./LICENSE /app
EXPOSE 80

ENTRYPOINT ["nginx","-g","daemon off;"]
