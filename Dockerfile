# Use an official Python runtime as a parent image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /usr/src/app


# Install system dependencies required by geopandas, rasterio
RUN apt-get update && apt-get install -y \
    libgdal-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy python packages list to install
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Copy the current directory contents into the container at /usr/src/app
COPY app.py templates .

# Define environment variable if needed
#ENV DATABASE_URL="your-database-url"
#ENV API_KEY="your-api-key"

# Run app.py when the container launches
CMD ["python", "app.py"]


#Personal
#2. docker build -t environmental-analysis-app .
# Run the docker container
#3. docker run -p 5000:5000 environmental-analysis-app
# Acces the app
#4. http://localhost:5000/
