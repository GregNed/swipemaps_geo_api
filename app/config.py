import os


class Config:
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = os.environ['SECRET_KEY']
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    VALIDATE_RESPONSES = True
    # The cartographic projection used to store and operate on spatial data
    PROJECTION = 32637  # https://epsg.io/32637
    # Business logic parameters
    CANDIDATE_DISTANCE_LIMIT = 30000
    ORS_MAX_ALTERNATIVES = 3
    MAX_PREPARED_ROUTES = 2
    DROPOFF_RADIUS = 150  # in meters
    POINT_PROXIMITY_THRESHOLD = 1000  # in meters


class ProductionConfig(Config):
    DEBUG = False
    VALIDATE_RESPONSES = False


class StagingConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
