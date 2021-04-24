FROM python:3.9-slim

RUN apt-get update && apt-get upgrade -y && apt-get autoremove -y

RUN python -m pip install --upgrade pip

RUN pip install requests django djangorestframework openrouteservice

WORKDIR app/

COPY . .

EXPOSE 8000

ENTRYPOINT ["python", "manage.py"]

CMD ["runserver"]