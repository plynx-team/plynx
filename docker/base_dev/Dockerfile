# Use an Plynx Base runtime as a parent image
FROM khaxis/plynx:base

# make sure the package is not available from build file
RUN pip uninstall plynx -y

RUN pip install watchdog==0.9.0

COPY ./scripts/watch.sh /app/watch.sh
ENV PLYNX_CONFIG=/app/config.yaml

ENTRYPOINT sh /app/watch.sh
