# Build the web ui first, only its output goes into the app image
FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app, and the built ui where Flask looks for it
COPY . /app
COPY --from=ui /ui/dist /app/frontend/dist

# Install the app and its pinned dependencies (editable, the app finds data/fish.db next to the package)
RUN pip install --no-cache-dir -e .

# The app runs as its own user, which can only write to its database and backups
RUN useradd --system --no-create-home fishtank \
    && mkdir -p /app/instance /app/backups \
    && chown fishtank:fishtank /app/instance /app/backups
USER fishtank

# The app's own database, made from data/fish.db on the first start, mount a volume here to keep it
ENV FISHTANK_DATABASE=/app/instance/fishtank.db
VOLUME /app/instance /app/backups

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Slim images have no curl, a failed read of the database marks the container unhealthy
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/readyz', timeout=4)"]

# Serve the app and the web ui with gunicorn when the container launches, gunicorn.conf.py has the settings
CMD ["gunicorn", "fishtank:create_app()"]
