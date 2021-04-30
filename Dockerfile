FROM python:3.9-slim

WORKDIR app/

RUN apt-get update && apt-get upgrade -y && apt-get autoremove -y

RUN pip install --upgrade pip

RUN pip install requests django djangorestframework openrouteservice psycopg2-binary

ENTRYPOINT ["python", "manage.py"]

CMD ["runserver", "0.0.0.0:8000"]

COPY . .