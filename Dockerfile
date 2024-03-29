# syntax=docker/dockerfile:1

FROM python:3.9-slim
# Reduce image size by not writing .pyc files
ENV PYTHONDONTWRITEBYTECODE 1
# Flush stdout straight to logs
ENV PYTHONUNBUFFERED 1
# Install curl for healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl
RUN pip install --upgrade pip

WORKDIR app/

HEALTHCHECK --start-period=5s --interval=5s --timeout=2s --retries=3 \
    CMD ["curl",  "http://localhost:5000"]

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "run", "--bind=0.0.0.0:5000", "-w 4", "app:app"]
