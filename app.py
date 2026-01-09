from flask import Flask
from config import *
from models.db import mysql
from routes.auth_routes import auth
from routes.post_routes import post
from routes.admin_routes import admin

app = Flask(__name__)
app.config.from_object('config')

mysql.init_app(app)

app.register_blueprint(auth)
app.register_blueprint(post)
app.register_blueprint(admin)

if __name__ == "__main__":
    app.run(debug=True)
