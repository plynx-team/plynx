# Use an official Python runtime as a parent image
FROM python:2.7-slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD ./docker/base/requirements.txt /app
ADD ./docker/base/test_config.yaml /app/config.yaml

# Install needed packages
RUN apt-get update
RUN apt-get install -y \
    build-essential \
    iputils-ping \
    curl \
    bc

RUN pip install --upgrade pip
RUN pip install --trusted-host pypi.python.org -r /app/requirements.txt

# Clean up
RUN rm /app/requirements.txt