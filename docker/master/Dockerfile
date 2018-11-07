# Use an official Python runtime as a parent image
FROM khaxis/plynx:base

# Set the working directory to /app
WORKDIR /app

# Make port ports available to the world outside this container
EXPOSE 10000

# Run app.py when the container launches
ENTRYPOINT python -m plynx.bin master -vvv
