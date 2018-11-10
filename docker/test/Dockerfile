# Use an Plynx Base runtime as a parent image
FROM khaxis/plynx:base

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD ./docker/test/scripts /app/scripts
ADD ./docker/test/data_00 /app/data_00

ENV PYTHONPATH "${PYTHONPATH}:/app"
ENV PLYNX_ENDPOINT "http://backend:5000/plynx/api/v0"

# Run app.py when the container launches
ENTRYPOINT ./scripts/run_tests.sh
