from dotenv import load_dotenv
import os
from datetime import timedelta

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.getenv('POSTGRES_URL')
    PERMANENT_SESSION_LIFETIME = timedelta(days=3)

class DevelopmentConfig(Config):
    SERVER_NAME = 'localhost:5000'
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

#imp