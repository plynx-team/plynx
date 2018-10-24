# Use an official Python runtime as a parent image
FROM python:2.7-slim

# Set the working directory to /app
WORKDIR /app

# Install needed packages
RUN apt-get update
RUN apt-get install -y \
    build-essential \
    iputils-ping \
    curl \
    bc

# Copy the current directory contents into the container at /app
ADD ./docker/base/requirements.txt /app

RUN pip install --upgrade pip
RUN pip install --trusted-host pypi.python.org -r /app/requirements.txt

# Copy config
ADD ./docker/base/test_config.yaml /app/config.yaml

# Clean up
RUN rm /app/requirements.txt

# Copy the current directory contents into the container at /app
ADD ./plynx /app/plynx
ADD ./wsgi.py /app/wsgi.py
