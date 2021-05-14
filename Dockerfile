FROM python:3.9-slim

RUN apt-get update && \
    apt-get --no-install-recommends upgrade -y && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

ENV FLASK_APP=api/api

RUN pip install --upgrade pip

WORKDIR app/

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD ["flask", "run", "--host=0.0.0.0"]