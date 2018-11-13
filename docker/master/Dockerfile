# Use an Plynx Base runtime as a parent image
FROM khaxis/plynx:base

# Set the working directory to /app
WORKDIR /app

# Make port ports available to the world outside this container
EXPOSE 17011

# Run app.py when the container launches
ENTRYPOINT plynx master -vvv
