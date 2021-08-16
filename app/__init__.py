import os
import re

import connexion
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from jsonschema import draft4_format_checker


uuid_regex = re.compile('^[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}\Z', re.I)


@draft4_format_checker.checks('uuid')
def is_uuid(value):
    return uuid_regex.match(value)


@draft4_format_checker.checks('latlon')
def is_latlon(value):
    try:
        lat, lon = map(float, value.split(','))
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except ValueError:
        return False


connexion_app = connexion.App(__name__)
app = connexion_app.app
env = os.getenv("FLASK_ENV", 'development')
app.config.from_object(f'app.config.{env.capitalize()}Config')
db = SQLAlchemy(app)
migrate = Migrate(app, db)
# Must come last bc it jumps to init another module & will cause partial initialization
connexion_app.add_api('swagger.yml', arguments={
    'pickup_point_proximity_threshold': app.config['PICKUP_POINT_PROXIMITY_THRESHOLD']
})
