# Use an official Python runtime as a parent image
FROM python:2.7-slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD . /app

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r ./docker/worker/requirements.txt
RUN useradd -c "Worker" worker  -s /bin/bash
RUN chmod 700 /app

# Make port 10000 available to the world outside this container
EXPOSE 10000

# Run app.py when the container launches
CMD ["python", "-m", "backend.worker", "-vvv"]
