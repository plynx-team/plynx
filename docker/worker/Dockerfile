# Use an Plynx Base runtime as a parent image
FROM khaxis/plynx:base

# Set the working directory to /app
WORKDIR /app

# Create worker user
RUN useradd -c "Worker" worker  -s /bin/bash
RUN chmod 700 /app
RUN chmod 1777 /tmp

# Make port ports available to the world outside this container
EXPOSE 17011

# Run app.py when the container launches
ENTRYPOINT plynx worker -vvv --host master
