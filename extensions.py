from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
login_manager = LoginManager()

login_manager.login_view = "login"
login_manager.login_message = "Bu sayfayı görüntülemek için giriş yapmalısın."
login_manager.login_message_category = "info"
