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
    mongo-tools

# Copy config
ADD ./config.yaml /app/config.yaml

# Copy the current directory contents into the container at /app
ADD ./wsgi.py /app/wsgi.py

# Copy licence
ADD ./LICENSE /app

# Copy test data
ADD ./docker/backend/scripts /app/scripts
ADD ./docker/backend/test_data /app/test_data

# master / worker port
EXPOSE 17011

# backend port
EXPOSE 5000

# Create worker user
RUN useradd -c "Worker" worker  -s /bin/bash
RUN chmod 700 /app
RUN chmod 1777 /tmp

# Add dev watch script
COPY ./scripts/watch.sh /app/watch.sh

# Build PLynx package
ADD ./plynx /tmp/plynx
ADD ./setup.py /tmp/setup.py
RUN cd /tmp && python setup.py install

# install extra docker requirements
ADD ./docker/backend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
RUN rm /app/requirements.txt