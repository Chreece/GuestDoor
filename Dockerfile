# Use a lightweight Python image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy all necessary files
COPY requirements.txt .
COPY app.py .
COPY frontend /app/frontend

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port Flask runs on
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]