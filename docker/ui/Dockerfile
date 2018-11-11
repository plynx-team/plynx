# Use an Plynx Base runtime as a parent image
FROM node:8-slim

# Set the working directory to /app
WORKDIR /app

ADD ./plynx-web /app
RUN npm install -s


ENTRYPOINT npm start
