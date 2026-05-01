from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.db import mysql
import MySQLdb.cursors

admin = Blueprint('admin', __name__, url_prefix='/admin')

# ----------------- ADMIN LOGIN -----------------
@admin.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM admins WHERE email=%s", (email,))
        admin_user = cur.fetchone()
        cur.close()

        # TEMP: plain password check (hash later)
        if admin_user and admin_user['password'] == password:
            session['admin_id'] = admin_user['id']
            session['admin_name'] = admin_user['name']
            flash(f"Welcome, {admin_user['name']}!", "success")
            return redirect(url_for('admin.dashboard'))

        flash("Invalid admin credentials", "danger")

    return render_template('admin_login.html')

# ----------------- ADMIN DASHBOARD -----------------
@admin.route('/dashboard')
def dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ----------------- ARTISTS -----------------
    cur.execute("""
        SELECT id, name, email, status
        FROM artists
        ORDER BY id DESC
    """)
    artists = cur.fetchall()

    # ----------------- USERS -----------------
    cur.execute("""
        SELECT id, username, email, role, status
        FROM users
        ORDER BY id DESC
    """)
    users = cur.fetchall()

    # ----------------- USER POSTS -----------------
    cur.execute("""
        SELECT p.id, p.content, p.media_filename, p.sentiment, p.created_at,
               u.username AS author_name
        FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
    """)
    user_posts = cur.fetchall()

    # ----------------- ARTIST POSTS -----------------
    cur.execute("""
        SELECT ap.id, ap.content, ap.media_filename, ap.sentiment, ap.created_at,
               a.name AS author_name
        FROM artist_posts ap
        JOIN artists a ON ap.artist_id = a.id
        ORDER BY ap.created_at DESC
    """)
    artist_posts = cur.fetchall()

    # ----------------- COMMENTS -----------------
    cur.execute("""
        SELECT 
            c.id,
            c.comment,
            c.sentiment,
            c.created_at,
            COALESCE(u.username, a.name, 'Unknown') AS author_name,
            c.role AS author_type,
            COALESCE(p.content, ap.content, 'Deleted Post') AS post_content
        FROM post_comments c
        LEFT JOIN users u ON c.user_id = u.id
        LEFT JOIN artists a ON c.user_id = a.id
        LEFT JOIN posts p ON c.post_id = p.id
        LEFT JOIN artist_posts ap ON c.post_id = ap.id
        ORDER BY c.created_at DESC
    """)
    comments = cur.fetchall()

    # ----------------- REACTIONS (USERS + ARTISTS) -----------------
    cur.execute("""
        SELECT * FROM (
            -- User likes
            SELECT 
                l.id,
                u.username AS author_name,
                'user' AS author_type,
                p.content AS post_content,
                'like' AS reaction,
                l.created_at
            FROM likes l
            JOIN users u ON l.user_id = u.id
            JOIN posts p ON l.post_id = p.id

            UNION ALL

            -- Artist likes
            SELECT 
                pl.id,
                a.name AS author_name,
                'artist' AS author_type,
                ap.content AS post_content,
                'like' AS reaction,
                pl.created_at
            FROM post_likes pl
            JOIN artist_posts ap ON pl.post_id = ap.id
            JOIN artists a ON ap.artist_id = a.id
        ) AS all_reactions
        ORDER BY created_at DESC
    """)
    reactions = cur.fetchall()
    #----------fanletters-----------------
    cur.execute("""
    SELECT 
    f.id,
    f.message,
    f.sentiment,
    f.sent_at,
    f.media_filename,
    f.media_type,
    f.artist_name AS artist,
    u.username AS sender
    FROM fan_letters f
    LEFT JOIN users u ON f.user_id = u.id
    ORDER BY f.sent_at DESC
    """)

    fanletters = cur.fetchall()
    # ----------------- ADMIN INFO -----------------
    cur.execute("""
        SELECT id, name, email
        FROM admins
        WHERE id=%s
    """, (session['admin_id'],))
    admin_info = cur.fetchone()

    cur.close()

    return render_template(
    "admin_dashboard.html",
    artists=artists,
    users=users,
    user_posts=user_posts,
    artist_posts=artist_posts,
    comments=comments,
    reactions=reactions,
    fanletters=fanletters,
    admin=admin_info
)
# ----------------- DELETE USER -----------------
@admin.route('/user/delete/<int:user_id>')
def delete_user(user_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    mysql.connection.commit()
    cur.close()

    flash("User deleted successfully", "success")
    return redirect(url_for('admin.dashboard'))

# ----------------- DELETE ARTIST -----------------
@admin.route('/artist/delete/<int:artist_id>')
def delete_artist(artist_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM artists WHERE id=%s", (artist_id,))
    mysql.connection.commit()
    cur.close()

    flash("Artist deleted successfully", "success")
    return redirect(url_for('admin.dashboard'))

# ----------------- DELETE POST -----------------
@admin.route('/post/delete/<int:post_id>')
def delete_post(post_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM posts WHERE id=%s", (post_id,))
    mysql.connection.commit()
    cur.close()

    flash("Post deleted successfully", "success")
    return redirect(url_for('admin.dashboard'))

# ----------------- DELETE REACTION -----------------
@admin.route('/reaction/delete/<int:reaction_id>')
def delete_reaction(reaction_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM reactions WHERE id=%s", (reaction_id,))
    mysql.connection.commit()
    cur.close()

    flash("Reaction deleted successfully", "success")
    return redirect(url_for('admin.dashboard'))

# ----------------- TOGGLE USER STATUS -----------------
@admin.route('/user/toggle/<int:user_id>')
def toggle_user_status(user_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT status FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    if not user:
        flash("User not found", "danger")
        return redirect(url_for('admin.dashboard'))

    new_status = 'blocked' if user['status'] == 'active' else 'active'
    cur.execute("UPDATE users SET status=%s WHERE id=%s", (new_status, user_id))
    mysql.connection.commit()
    cur.close()

    flash(f"User status changed to {new_status}", "success")
    return redirect(url_for('admin.dashboard'))

# ----------------- TOGGLE ARTIST STATUS -----------------
@admin.route('/artist/toggle/<int:artist_id>')
def toggle_artist_status(artist_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT status FROM artists WHERE id=%s", (artist_id,))
    artist = cur.fetchone()
    if not artist:
        flash("Artist not found", "danger")
        return redirect(url_for('admin.dashboard'))

    new_status = 'blocked' if artist['status'] == 'active' else 'active'
    cur.execute("UPDATE artists SET status=%s WHERE id=%s", (new_status, artist_id))
    mysql.connection.commit()
    cur.close()

    flash(f"Artist status changed to {new_status}", "success")
    return redirect(url_for('admin.dashboard'))

# ----------------- ADMIN LOGOUT -----------------
@admin.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for('admin.login'))
