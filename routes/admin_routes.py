from flask import Blueprint, render_template
from models.db import mysql

admin = Blueprint('admin', __name__)

@admin.route('/admin')
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM posts")
    posts = cur.fetchone()[0]

    return render_template('admin.html', users=users, posts=posts)
