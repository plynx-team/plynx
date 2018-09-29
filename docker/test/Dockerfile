# Use an official Python runtime as a parent image
FROM khaxis/plynx:base

# Set the working directory to /app
WORKDIR /app

# Install needed packages
RUN apt-get install -y \
    mongodb-clients

# Copy the current directory contents into the container at /app
ADD ./docker/test/scripts /app/scripts
ADD ./docker/test/data_00 /app/data_00
ADD ./plynx-python-client /app/plynx-python-client
ENV PYTHONPATH "${PYTHONPATH}:/app/plynx-python-client"
ENV PLYNX_ENDPOINT "http://backend:5000/plynx/api/v0"

# Run app.py when the container launches
ENTRYPOINT ./scripts/run_tests.sh
