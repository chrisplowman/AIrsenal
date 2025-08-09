FROM python:3.12-slim-bookworm
WORKDIR /airsenal
COPY . /airsenal
RUN apt-get update && \
    apt-get install build-essential git sqlite3 curl -y && \
    pip install --upgrade pip && \
    pip install .[dev,api] && \
    pip install flask gunicorn

# Expose the port that Render expects
EXPOSE 10000

# Default to web app, but allow override via environment variable
CMD ["sh", "-c", "if [ \"$RUN_MODE\" = \"pipeline\" ]; then airsenal_run_pipeline; else python web_app.py; fi"]
