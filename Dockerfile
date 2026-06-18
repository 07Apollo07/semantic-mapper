# Use a lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Define where projects are stored inside the container (matches the bind mount in compose)
ENV PROJECTS_DIR=/projects-display

# Ensure the projects directory exists at build time (also created at runtime if missing)
RUN mkdir -p "$PROJECTS_DIR"

# Install system dependencies required by some Python packages (e.g., pandas)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Create a virtual environment inside the image (keeps the global site‑packages clean)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies into the virtual environment
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt && \
	# Remove build‑time packages to keep the final image small
	apt-get purge -y --auto-remove gcc && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application code (the .dockerignore will prevent copying .venv and other junk)
COPY . .

# Expose the default Streamlit port (8501)
EXPOSE 8501

# Default command to run the Streamlit application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
