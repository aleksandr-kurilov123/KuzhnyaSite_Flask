from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv, find_dotenv
import os
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
from config import Config


# Load environment variables from .env file
load_dotenv(find_dotenv())

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'routes.login'

def create_app():
    app = Flask(__name__)

    env = os.getenv('FLASK_ENV')
    if env == 'development':
        app.config.from_object('config.DevelopmentConfig')
    else:
        app.config.from_object('config.ProductionConfig')

    # Ensure SQLALCHEMY_DATABASE_URI is set
    postgres_url = os.getenv("TEST_POSTGRES_URL")
    if not postgres_url:
        raise ValueError("TEST_POSTGRES_URL is not set")

    # Parse and clean the connection string
    raw_url = postgres_url.replace("postgres://", "postgresql+psycopg2://")
    url_parts = urlparse(raw_url)
    query = parse_qs(url_parts.query)
    query.pop('supa', None)  # Remove the 'supa' parameter
    cleaned_query = urlencode(query, doseq=True)
    cleaned_url = urlunparse((url_parts.scheme, url_parts.netloc, url_parts.path, url_parts.params, cleaned_query, url_parts.fragment))

    app.config['SQLALCHEMY_DATABASE_URI'] = cleaned_url

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf = CSRFProtect(app)

    from .models import Users

    @login_manager.user_loader
    def load_user(user_id):
        return Users.query.get(int(user_id))
    
    with app.app_context():
        db.create_all()
    
    from .routes import routes
    app.register_blueprint(routes)

    return app
