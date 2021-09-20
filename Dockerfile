FROM python:3.9-slim

RUN apt-get update && \
    apt-get --no-install-recommends upgrade -y && \
    apt-get install -y curl && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

WORKDIR app/

HEALTHCHECK --start-period=10s --interval=3s --timeout=3s --retries=3 \
    CMD ["curl",  "http://localhost:5000"]

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "run", "--bind=0.0.0.0:5000", "-w 4", "app:app"]