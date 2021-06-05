import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
env = os.getenv("FLASK_ENV", 'development')
app.config.from_object(f'api.config.{env.capitalize()}Config')
db = SQLAlchemy(app)
migrate = Migrate(app, db)

from api import routes  # noqa: E402
