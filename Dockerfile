#sample
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r requirements.txt

# The app's own database, made from data/fish.db on the first start, mount a volume here to keep it
ENV FISHTANK_DATABASE=/app/instance/fishtank.db
VOLUME /app/instance

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Serve the app with gunicorn when the container launches
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:create_app()"]
