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

# The app's own database, made from data/fish.db on the first start, mount a volume here to keep it
ENV FISHTANK_DATABASE=/app/instance/fishtank.db
VOLUME /app/instance

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Serve the app and the web ui with gunicorn when the container launches
CMD ["gunicorn", "-b", "0.0.0.0:5000", "fishtank:create_app()"]
