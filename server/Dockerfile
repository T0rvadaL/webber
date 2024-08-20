# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run hypercorn with your FastAPI app
CMD ["hypercorn", "app:app", "--bind", "0.0.0.0:8000", "--certfile", "./cert.pem", "--keyfile", "./key.pem", "--ca-certs", "./cert.pem"]