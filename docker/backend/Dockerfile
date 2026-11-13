# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory to /app
WORKDIR /app

# Install needed packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    curl \
    bc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the current directory contents into the container at /app
COPY ./wsgi.py /app/wsgi.py

# Copy licence
COPY ./LICENSE /app

# Copy test data
COPY ./docker/backend/tests /app/integrated_tests

# master / worker port
EXPOSE 17011

# backend port
EXPOSE 5005

# Create worker user
RUN useradd -c "Worker" worker -s /bin/bash \
    && chmod 700 /app \
    && chmod 1777 /tmp

# Add dev watch script
COPY ./scripts/watch.sh /app/watch.sh
COPY ./scripts/run_tests.sh /app/run_tests.sh

# Build PLynx package
COPY ./plynx /tmp/build/plynx
COPY ./setup.py /tmp/build/setup.py
COPY ./pyproject.toml /tmp/build/pyproject.toml
COPY ./MANIFEST.in /tmp/build/MANIFEST.in
COPY ./README.md /tmp/build/README.md
COPY ./LICENSE /tmp/build/LICENSE
COPY ./requirements.txt /tmp/build/requirements.txt
COPY ./requirements-dev.txt /tmp/build/requirements-dev.txt
COPY ./tests /app/tests
RUN pip install --no-cache-dir /tmp/build && rm -rf /tmp/build

# Install extra docker requirements
COPY ./docker/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && rm /app/requirements.txt
RUN echo '[]' > /app/nodes.json
