import os

import connexion
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from jsonschema import draft4_format_checker


@draft4_format_checker.checks('latlon')
def is_latlon(value):
    lat, lon = map(float, value.split(','))
    return -90 <= lat <= 90 and -180 <= lon <= 180


connexion_app = connexion.App(__name__)
app = connexion_app.app
env = os.getenv('FLASK_ENV', 'development')
app.config.from_object(f'app.config.{env.capitalize()}Config')
db = SQLAlchemy(app)
migrate = Migrate(app, db)
# Must come last bc it jumps to init another module & will cause partial initialization
ma = Marshmallow(connexion_app)
connexion_app.add_api(
    'swagger.yml',
    strict_validation=True,
    # validate_responses=app.config['VALIDATE_RESPONSES'],
    arguments={'config': app.config}
)
