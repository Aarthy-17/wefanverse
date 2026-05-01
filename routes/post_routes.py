from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.db import mysql
import MySQLdb.cursors
from datetime import datetime
import os
from werkzeug.utils import secure_filename

post = Blueprint('post', __name__, url_prefix='/post')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ----------------- COMMUNITY FEED -----------------
@post.route('/feed', methods=['GET', 'POST'])
def feed():
    if 'user_id' not in session:
        flash("Login to access the feed", "warning")
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # -----------------------
    # Handle new post
    # -----------------------
    if request.method == 'POST':
        content = request.form.get('content')
        media_file = request.files.get('media')
        filename = None
        media_type = None

        if media_file and allowed_file(media_file.filename):
            filename = secure_filename(media_file.filename)
            media_file.save(os.path.join(UPLOAD_FOLDER, filename))
            ext = filename.rsplit('.', 1)[1].lower()
            media_type = 'video' if ext in ['mp4', 'mov', 'avi'] else 'image'

        cur.execute("""
            INSERT INTO posts (user_id, content, media_filename, media_type, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, content, filename, media_type, datetime.now()))

        mysql.connection.commit()
        flash("Post shared!", "success")
        return redirect(url_for('post.feed'))

    # -----------------------
    # FETCH POSTS
    # -----------------------
    cur.execute("""
        SELECT p.id AS post_id,
               p.user_id,
               p.content,
               p.media_filename,
               p.media_type,
               p.created_at,
               p.is_ad,
               u.username
        FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY 
            CASE WHEN p.is_ad = 1 THEN 0 ELSE 1 END,
            p.id DESC
    """)
    posts = cur.fetchall()

    # -----------------------
    # Attach comments & reactions
    # -----------------------
    for p in posts:
        # Comments
        cur.execute("""
            SELECT c.comment, u.username, c.created_at
            FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.post_id=%s
            ORDER BY c.id ASC
        """, (p['post_id'],))
        p['comments'] = cur.fetchall()

        # Reactions
        cur.execute("""
            SELECT reaction, COUNT(*) AS count
            FROM reactions
            WHERE post_id=%s
            GROUP BY reaction
        """, (p['post_id'],))
        p['reactions'] = cur.fetchall()

    # -----------------------
    # 🔥 USER STATS SECTION
    # -----------------------

    # Total Posts
    cur.execute("SELECT COUNT(*) AS total_posts FROM posts WHERE user_id=%s", (user_id,))
    total_posts = cur.fetchone()['total_posts']

    # Followers count
    cur.execute("SELECT COUNT(*) AS total_followers FROM followers WHERE followed_id=%s", (user_id,))
    total_followers = cur.fetchone()['total_followers']

    # Following count
    cur.execute("SELECT COUNT(*) AS total_following FROM followers WHERE follower_id=%s", (user_id,))
    total_following = cur.fetchone()['total_following']

    stats = {
        "posts": total_posts,
        "followers": total_followers,
        "following": total_following
    }

    cur.close()

    return render_template('feed.html', posts=posts, stats=stats)


# ----------------- ADD COMMENT -----------------
@post.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    comment = request.form.get('comment')
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO comments (post_id, user_id, comment, created_at)
        VALUES (%s, %s, %s, %s)
    """, (post_id, session['user_id'], comment, datetime.now()))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('post.feed'))


# ----------------- REACT -----------------
@post.route('/react/<int:post_id>', methods=['POST'])
def react_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    reaction = request.form.get('reaction')
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM reactions WHERE post_id=%s AND user_id=%s",
                (post_id, session['user_id']))
    existing = cur.fetchone()

    if existing:
        cur.execute("UPDATE reactions SET reaction=%s WHERE id=%s",
                    (reaction, existing[0]))
    else:
        cur.execute("""
            INSERT INTO reactions (post_id, user_id, reaction, created_at)
            VALUES (%s, %s, %s, %s)
        """, (post_id, session['user_id'], reaction, datetime.now()))

    mysql.connection.commit()
    cur.close()
    return redirect(url_for('post.feed'))


# ----------------- FAN LETTERS -----------------
@post.route('/fan_letters', methods=['GET', 'POST'])
def send_fan_letter():
    if 'user_id' not in session:
        flash("Login to send a fan letter", "warning")
        return redirect(url_for('auth.login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        artist_name = request.form.get('artist_name')
        message = request.form.get('message')
        media_file = request.files.get('media_file')
        filename = None
        media_type = None

        if media_file and allowed_file(media_file.filename):
            filename = secure_filename(media_file.filename)
            media_file.save(os.path.join(UPLOAD_FOLDER, filename))
            ext = filename.rsplit('.', 1)[1].lower()
            media_type = 'video' if ext in ['mp4','mov','avi'] else 'image'

        cur.execute("""
            INSERT INTO fan_letters (user_id, artist_name, message, media_filename, media_type, sent_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (session['user_id'], artist_name, message, filename, media_type))

        mysql.connection.commit()
        flash("Fan letter sent successfully!", "success")
        return redirect(url_for('post.send_fan_letter'))

    # Fetch user's sent letters
    cur.execute("SELECT * FROM fan_letters WHERE user_id=%s ORDER BY sent_at DESC", (session['user_id'],))
    letters = cur.fetchall()
    cur.close()

    return render_template('fan_letters.html', letters=letters)
