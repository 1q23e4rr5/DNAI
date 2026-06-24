from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
socketio = SocketIO(cors_allowed_origins="*")


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'my-super-secret-key-2024')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../instance/number_detection.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('instance', exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'لطفاً وارد شوید.'
    bcrypt.init_app(app)
    socketio.init_app(app)

    from app import routes, admin_routes
    app.register_blueprint(routes.bp)
    app.register_blueprint(admin_routes.admin_bp, url_prefix='/admin')

    from app.tasks import start_scheduler
    start_scheduler(app)

    return app


__all__ = ['create_app', 'socketio', 'db', 'migrate', 'login_manager', 'bcrypt']