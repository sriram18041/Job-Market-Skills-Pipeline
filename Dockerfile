FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so Docker can cache this layer across builds
# where only the source code (not requirements.txt) changed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY sql/ ./sql/
COPY dashboard/ ./dashboard/

WORKDIR /app/src
ENTRYPOINT ["python", "pipeline.py"]
