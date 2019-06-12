# Use an Plynx Base runtime as a parent image
FROM node:12.4.0-alpine

# Set the working directory to /app
WORKDIR /app

# Copy files
ADD ./ui/README.md          /app
ADD ./ui/package-lock.json  /app
ADD ./ui/package.json       /app
ADD ./ui/public             /app/public
ADD ./ui/src                /app/src

# Copy licence
ADD ./LICENSE /app

# Build
RUN npm install

# Build code for production
# RUN npm ci --only=production

# Bundle app source
COPY . .

# Make port ports available to the world outside this container
EXPOSE 3000

ENTRYPOINT npm start
