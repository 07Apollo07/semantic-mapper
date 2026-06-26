# Use a lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Define where projects are stored inside the container.
# This defaults to the path the application expects when running in Docker.
# It can still be overridden at build time with `--build-arg PROJECTS_DIR=…` if needed.
ARG PROJECTS_DIR=/app/project-display
ENV PROJECTS_DIR=${PROJECTS_DIR}

# Optional MCP enable flag – defaults to disabled. Override via .env or docker‑compose.
ENV mcp_enable=False

# Ensure the projects directory exists at build time (and will also exist at runtime
# if the host does not mount a volume over it).
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

# Expose the default Streamlit port (8501) and optional MCP HTTP port (8000)
EXPOSE 8501 8000

# Copy an entrypoint script that will launch Streamlit and optionally the MCP server
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Default command runs the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
