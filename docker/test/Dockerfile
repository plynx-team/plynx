# Use an official Python runtime as a parent image
FROM khaxis/plynx:base

# Set the working directory to /app
WORKDIR /app

# Install needed packages
RUN apt-get install -y \
    mongodb-clients

# Copy the current directory contents into the container at /app
ADD ./docker/test/scripts /app/scripts


# Run app.py when the container launches
ENTRYPOINT ./scripts/run_tests.sh
