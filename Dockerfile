FROM python:3.9-slim

RUN apt-get update && \
    apt-get --no-install-recommends upgrade -y && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv

RUN python -m venv $VIRTUAL_ENV

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip

WORKDIR app/

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

ENTRYPOINT ["python", "manage.py"]

CMD ["runserver", "0.0.0.0:8000"]