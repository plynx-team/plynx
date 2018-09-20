# Use an official Python runtime as a parent image
FROM khaxis/plynx:base

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD ./constants /app/constants
ADD ./core /app/core
ADD ./graph /app/graph
ADD ./utils /app/utils

# Create worker user
RUN useradd -c "Worker" worker  -s /bin/bash
RUN chmod 700 /app
RUN chmod 1777 /tmp

# Make port ports available to the world outside this container
EXPOSE 10000

# Run app.py when the container launches
ENTRYPOINT python -m core.worker -vvv --host host.docker.internal
