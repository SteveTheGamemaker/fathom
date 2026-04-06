FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cacheable layer)
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy source
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./

# Re-install with source (editable not needed in production)
RUN pip install --no-cache-dir .

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8989

ENV FATHOM_DATABASE__PATH=/app/data/fathom.db

CMD ["python", "-m", "uvicorn", "fathom.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8989"]
