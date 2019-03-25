# Use an official Python runtime as a parent image
FROM python:3.7-slim

# Set the working directory to /app
WORKDIR /app

# Install needed packages
RUN apt-get update
RUN apt-get install -y \
    build-essential \
    iputils-ping \
    curl \
    bc \
    mongodb-clients

# Copy config
ADD ./docker/base/test_config.yaml /app/config.yaml

# Copy the current directory contents into the container at /app
ADD ./wsgi.py /app/wsgi.py

# Copy licence
ADD ./LICENSE /app

# Build PLynx package
ADD ./plynx /tmp/plynx
ADD ./setup.py /tmp/setup.py
RUN cd /tmp && python setup.py install
