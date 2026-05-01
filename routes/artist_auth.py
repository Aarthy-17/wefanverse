from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models.db import mysql
import MySQLdb.cursors
from datetime import datetime, timedelta
import os

artist_auth = Blueprint('artist_auth', __name__, url_prefix='/artist')

UPLOAD_FOLDER = 'static/uploads'

# ================= REGISTER =================
@artist_auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower()
        password = request.form['password']

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT id FROM artists WHERE email=%s", (email,))
        if cur.fetchone():
            flash("Artist already exists", "warning")
            return redirect(url_for('artist_auth.register'))

        cur.execute(
            "INSERT INTO artists (name,email,password) VALUES (%s,%s,%s)",
            (name, email, generate_password_hash(password))
        )
        mysql.connection.commit()
        cur.close()

        flash("Artist registered 🎤", "success")
        return redirect(url_for('artist_auth.login'))

    return render_template('artist_register.html')

# ================= LOGIN =================
@artist_auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM artists WHERE email=%s", (email,))
        artist = cur.fetchone()
        cur.close()

        if artist and check_password_hash(artist['password'], password):
            session['artist_id'] = artist['id']
            session['artist_name'] = artist['name']
            return redirect(url_for('artist_auth.dashboard'))

        flash("Invalid credentials", "danger")

    return render_template('artist_login.html')

# ================= DASHBOARD =================
@artist_auth.route('/dashboard')
def dashboard():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    artist_id = session['artist_id']
    artist_name = session['artist_name']
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ---------------- POSTS ----------------
    cur.execute("""
        SELECT * 
        FROM artist_posts 
        WHERE artist_id=%s 
        ORDER BY created_at DESC
    """, (artist_id,))
    posts = cur.fetchall()

    for post in posts:
        cur.execute("SELECT COUNT(*) AS c FROM likes WHERE post_id=%s", (post['id'],))
        post['likes'] = cur.fetchone()['c']

        cur.execute("SELECT COUNT(*) AS c FROM reactions WHERE post_id=%s", (post['id'],))
        post['reactions'] = cur.fetchone()['c']

    # ---------------- STATS ----------------
    cur.execute("SELECT COUNT(*) AS c FROM artist_posts WHERE artist_id=%s", (artist_id,))
    post_count = cur.fetchone()['c']

    cur.execute("""
    SELECT COUNT(*) AS c
    FROM user_follows
    WHERE artist_id=%s
    """, (artist_id,))
    fan_count = cur.fetchone()['c']

    cur.execute("""
    SELECT COUNT(*) AS c
    FROM post_likes pl
    JOIN artist_posts ap ON pl.post_id = ap.id
    WHERE ap.artist_id = %s
    """, (artist_id,))
    likes_count = cur.fetchone()['c']

    cur.execute("""
    SELECT u.username
    FROM user_follows uf
    JOIN users u ON u.id = uf.user_id
    WHERE uf.artist_id = %s
    ORDER BY uf.created_at DESC
    """, (artist_id,))
    followers = cur.fetchall()
    # ---------------- FAN LETTERS ----------------
    artist_id = session['artist_id']
    artist_name = session['artist_name']

    cur.execute("""
    SELECT l.id, l.artist_id, l.artist_name, l.message,
           l.media_filename, l.media_type, l.sent_at, u.username
    FROM fan_letters l
    LEFT JOIN users u ON l.user_id = u.id
    WHERE l.artist_id = %s
       OR l.artist_name = %s
       OR l.message LIKE '%%BTS%%'
    ORDER BY l.sent_at DESC
    """, (artist_id, artist_name))




    letters = cur.fetchall()
    
    cur.close()

    return render_template(
    'artist_dashboard.html',
    artist_name=artist_name,
    posts=posts,
    post_count=post_count,
    fan_count=fan_count,
    likes_count=likes_count,
    followers=followers,
    letters=letters
)

# ================= VIEW FAN LETTER =================
@artist_auth.route('/letter/<int:letter_id>')
def view_letter(letter_id):
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    artist_id = session['artist_id']
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT l.*, u.username 
        FROM fan_letters l
        LEFT JOIN users u ON l.user_id = u.id
        WHERE l.id = %s AND l.artist_id = %s
    """, (letter_id, artist_id))
    letter = cur.fetchone()
    cur.close()

    if not letter:
        flash("Letter not found or you don't have permission to view it", "warning")
        return redirect(url_for('artist_auth.dashboard'))

    return render_template("artist_view_letter.html", letter=letter)

# ================= SETTINGS =================
@artist_auth.route('/settings')
def settings():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    artist_id = session['artist_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM artists WHERE id = %s", (artist_id,))
    artist = cursor.fetchone()
    cursor.close()

    return render_template("artist_settings.html", artist=artist)

# ================= PRIVACY SETTINGS =================
@artist_auth.route('/privacy-settings', methods=['GET', 'POST'])
def privacy_settings():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if request.method == 'POST':
        is_private = 1 if request.form.get('is_private') else 0
        disable_fan_letters = 1 if request.form.get('disable_fan_letters') else 0
        cursor.execute("""
            UPDATE artists 
            SET is_private=%s, disable_fan_letters=%s 
            WHERE id=%s
        """, (is_private, disable_fan_letters, session['artist_id']))
        mysql.connection.commit()
        flash("Privacy settings updated successfully!", "success")

    cursor.execute("SELECT * FROM artists WHERE id=%s", (session['artist_id'],))
    artist = cursor.fetchone()
    cursor.close()

    return render_template('artist_privacy_settings.html', artist=artist)

# ================= MESSAGE CONTROLS =================
@artist_auth.route('/message_controls')
def artist_message_controls():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))
    return render_template("artist_message_controls.html")

# ================= ADS SETTINGS =================
@artist_auth.route('/ads_settings')
def artist_ads_settings():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT id, content, media_filename, created_at, is_boosted
        FROM artist_posts
        WHERE artist_id=%s AND is_boosted=1
        ORDER BY created_at DESC
    """, (session['artist_id'],))
    boosted_posts = cursor.fetchall()
    cursor.close()

    return render_template("artist_ads_settings.html", boosted_posts=boosted_posts)

# ================= SECURITY SETTINGS =================
@artist_auth.route('/security_settings')
def artist_security_settings():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))
    return render_template("artist_security_settings.html")

#----------feed-------------------------
# ================= ARTIST FEED =================
# ================= ARTIST FEED =================
@artist_auth.route('/feed')
def feed():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ------------------ Artist Posts ------------------
    cursor.execute("SELECT * FROM artist_posts ORDER BY created_at DESC")
    artist_posts = list(cursor.fetchall())  # <-- ensure it's a list

    for post in artist_posts:
        # Likes
        cursor.execute("SELECT COUNT(*) AS count FROM post_likes WHERE post_id = %s", (post['id'],))
        post['like_count'] = cursor.fetchone()['count']

        # Comments from artists
        cursor.execute("""
            SELECT pc.comment, a.name AS username
            FROM post_comments pc
            JOIN artists a ON pc.user_id = a.id
            WHERE pc.post_id = %s
            ORDER BY pc.created_at ASC
        """, (post['id'],))
        post['comments'] = list(cursor.fetchall())
        post['author_name'] = post['artist_name']

    # ------------------ User Posts ------------------
    cursor.execute("""
        SELECT p.*, u.username AS author_name
        FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY created_at DESC
    """)
    user_posts = list(cursor.fetchall())  # <-- ensure it's a list

    for post in user_posts:
        post['like_count'] = post['likes'] or 0
        # Comments for user posts
        cursor.execute("""
            SELECT pc.comment, u.username
            FROM post_comments pc
            JOIN users u ON pc.user_id = u.id
            WHERE pc.post_id = %s
            ORDER BY pc.created_at ASC
        """, (post['id'],))
        post['comments'] = list(cursor.fetchall())

    # ------------------ Merge & Sort ------------------
    all_posts = artist_posts + user_posts
    all_posts.sort(key=lambda x: x['created_at'], reverse=True)

    cursor.close()
    return render_template('artist_feed.html', posts=all_posts)
# ================= LIKE POST =================
@artist_auth.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'artist_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    artist_id = session['artist_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM post_likes WHERE post_id=%s AND user_id=%s", (post_id, artist_id))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("DELETE FROM post_likes WHERE post_id=%s AND user_id=%s", (post_id, artist_id))
    else:
        cursor.execute("INSERT INTO post_likes (post_id, user_id) VALUES (%s, %s)", (post_id, artist_id))

    mysql.connection.commit()
    cursor.execute("SELECT COUNT(*) AS count FROM post_likes WHERE post_id=%s", (post_id,))
    count = cursor.fetchone()['count']
    cursor.close()
    return jsonify({'likes': count})

# ================= ADD COMMENT =================
@artist_auth.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'artist_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    artist_id = session['artist_id']
    data = request.get_json(silent=True)

    if not data:
        return jsonify({'error': 'No data received'}), 400

    comment_text = data.get('comment', '').strip()
    if not comment_text:
        return jsonify({'error': 'Empty comment'}), 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("INSERT INTO post_comments (post_id, user_id, comment) VALUES (%s, %s, %s)",
                   (post_id, artist_id, comment_text))
    mysql.connection.commit()
    cursor.execute("SELECT name FROM artists WHERE id=%s", (artist_id,))
    artist = cursor.fetchone()
    cursor.close()

    return jsonify({'username': artist['name'], 'comment': comment_text})

# ================= DELETE POST =================
# ================= DELETE POST =================
@artist_auth.route('/delete-post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    # ✅ Check if artist is logged in
    if 'artist_id' not in session:
        flash("Please login to delete posts.", "warning")
        return redirect(url_for('artist_auth.login'))

    artist_id = session['artist_id']

    cursor = mysql.connection.cursor()
    # ✅ Delete only if post belongs to logged-in artist
    cursor.execute(
        "DELETE FROM artist_posts WHERE id=%s AND artist_id=%s",
        (post_id, artist_id)
    )
    deleted = cursor.rowcount  # ✅ Check if any row was actually deleted
    mysql.connection.commit()
    cursor.close()

    # ✅ Feedback to user
    if deleted > 0:
        flash("Post deleted successfully 🗑️", "success")
    else:
        flash("Cannot delete post: Post not found or not yours.", "danger")

    return redirect(url_for('artist_auth.dashboard'))
# ================= LIVE ARTISTS =================
@artist_auth.route('/live_artists')
def live_artists():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT id, name, bio FROM artists")
    artists = cursor.fetchall()
    return render_template("artist_live_artists.html", artists=artists)

# ================= ACCOUNT CENTER =================
@artist_auth.route('/account-center')
def account_center():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))
    return render_template('artist_account_center.html')

# ================= PERSONAL DETAILS =================
@artist_auth.route('/personal-details', methods=['GET', 'POST'])
def personal_details():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    artist_id = session['artist_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        cursor.execute("UPDATE artists SET name=%s, email=%s WHERE id=%s", (name, email, artist_id))
        mysql.connection.commit()
        flash("Details updated successfully!", "success")

    cursor.execute("SELECT * FROM artists WHERE id=%s", (artist_id,))
    artist = cursor.fetchone()
    return render_template('artist_personal_details.html', artist=artist)

# ================= PASSWORD SECURITY =================
@artist_auth.route('/password-security', methods=['GET', 'POST'])
def password_security():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM artists WHERE id=%s", (session['artist_id'],))
        artist = cursor.fetchone()

        if not artist or not check_password_hash(artist['password'], current_password):
            flash("Current password is incorrect!", "danger")
        elif new_password != confirm_password:
            flash("New passwords do not match!", "danger")
        else:
            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE artists SET password=%s WHERE id=%s", (hashed_password, session['artist_id']))
            mysql.connection.commit()
            flash("Password updated successfully!", "success")

        cursor.close()
        return redirect(url_for('artist_auth.password_security'))

    return render_template('artist_password_security.html')

# ================= TWO FACTOR AUTH =================
@artist_auth.route('/two-factor-auth', methods=['GET', 'POST'])
def two_factor_auth():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if request.method == 'POST':
        enable = request.form.get('enable_2fa')
        cursor.execute("UPDATE artists SET two_factor_enabled=%s WHERE id=%s",
                       (1 if enable == "on" else 0, session['artist_id']))
        mysql.connection.commit()
        flash("Two-Factor Authentication " + ("Enabled!" if enable == "on" else "Disabled!"),
              "success" if enable == "on" else "danger")
        return redirect(url_for('artist_auth.two_factor_auth'))

    cursor.execute("SELECT two_factor_enabled FROM artists WHERE id=%s", (session['artist_id'],))
    artist = cursor.fetchone()
    cursor.close()
    return render_template('artist_two_factor.html', artist=artist)

# ================= BOOST POST =================
@artist_auth.route('/boost-post/<int:post_id>', methods=['POST'])
def boost_post(post_id):
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    artist_id = session['artist_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT id FROM artist_posts WHERE id=%s AND artist_id=%s", (post_id, artist_id))
    post = cursor.fetchone()
    if not post:
        flash("You cannot boost this post!", "danger")
        return redirect(url_for('artist_auth.dashboard'))

    cursor.execute("UPDATE artist_posts SET is_boosted = IF(is_boosted=1, 0, 1) WHERE id=%s", (post_id,))
    mysql.connection.commit()
    cursor.close()

    flash("Post boost status updated 🚀", "success")
    return redirect(url_for('artist_auth.dashboard'))

# ================= ANALYTICS =================
@artist_auth.route('/analytics')
def analytics():
    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    artist_id = session['artist_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # PIE CHART DATA
    cursor.execute("SELECT COUNT(*) AS count FROM followers WHERE followed_id=%s AND followed_type='artist'", (artist_id,))
    followers = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM followers WHERE follower_id=%s AND followed_type='artist'", (artist_id,))
    following = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM artist_posts WHERE artist_id=%s", (artist_id,))
    posts_count = cursor.fetchone()['count']

    cursor.execute("""
        SELECT COUNT(reactions.id) AS count 
        FROM reactions
        JOIN artist_posts ON reactions.post_id = artist_posts.id
        WHERE artist_posts.artist_id=%s
    """, (artist_id,))
    reactions_count = cursor.fetchone()['count']

    # LINE CHART DAILY ENGAGEMENT
    last_7_days = [(datetime.now() - timedelta(days=i)).date() for i in range(6, -1, -1)]
    daily_labels = [d.strftime("%d %b") for d in last_7_days]
    daily_engagement = []
    for day in last_7_days:
        cursor.execute("""
            SELECT COUNT(reactions.id) AS count
            FROM reactions
            JOIN artist_posts ON reactions.post_id = artist_posts.id
            WHERE artist_posts.artist_id=%s AND DATE(reactions.created_at)=%s
        """, (artist_id, day))
        daily_engagement.append(cursor.fetchone()['count'])

    # BAR CHART POPULAR POSTS
    cursor.execute("""
        SELECT artist_posts.id AS post_id, artist_posts.content, COUNT(reactions.id) AS reaction_count
        FROM artist_posts
        LEFT JOIN reactions ON reactions.post_id = artist_posts.id
        WHERE artist_posts.artist_id=%s
        GROUP BY artist_posts.id
        ORDER BY reaction_count DESC
        LIMIT 5
    """, (artist_id,))
    popular_posts = cursor.fetchall()
    bar_labels = [post['content'][:20] + '...' if len(post['content']) > 20 else post['content'] for post in popular_posts]
    bar_values = [post['reaction_count'] for post in popular_posts]

    cursor.close()
    return render_template('artist_analytics.html',
                           followers=followers,
                           following=following,
                           posts=posts_count,
                           reactions=reactions_count,
                           daily_labels=daily_labels,
                           daily_engagement=daily_engagement,
                           bar_labels=bar_labels,
                           bar_values=bar_values)

#---------------artist notifications----------------
@artist_auth.route('/notifications')
def artist_notifications():

    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    artist_id = session['artist_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fan letters
    cursor.execute("""
        SELECT u.username, f.message, f.sent_at AS created_at, 'fanletter' AS type
        FROM fan_letters f
        JOIN users u ON f.user_id = u.id
        WHERE f.artist_id=%s
    """,(artist_id,))
    fanletters = cursor.fetchall()

    # Post likes
    cursor.execute("""
        SELECT u.username,
        'liked your post ❤️' AS message,
        pl.created_at,
        'like' AS type
        FROM post_likes pl
        JOIN artist_posts ap ON pl.post_id = ap.id
        JOIN users u ON pl.user_id = u.id
        WHERE ap.artist_id=%s
    """,(artist_id,))
    likes = cursor.fetchall()

    notifications = list(fanletters) + list(likes)

    notifications.sort(key=lambda x: x['created_at'], reverse=True)

    return render_template("artist_notifications.html", notifications=notifications)
#-----------artistprofile-----------------
@artist_auth.route('/artist_profile/<int:artist_id>')
def artist_profile(artist_id):

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Artist details
    cursor.execute("""
        SELECT *
        FROM artists
        WHERE id=%s
    """, (artist_id,))
    artist = cursor.fetchone()

    # Total posts
    cursor.execute("""
        SELECT COUNT(*) AS total_posts
        FROM artist_posts
        WHERE artist_id=%s
    """, (artist_id,))
    posts = cursor.fetchone()['total_posts']

    # Total likes on posts
    cursor.execute("""
        SELECT COUNT(*) AS total_likes
        FROM post_likes pl
        JOIN artist_posts ap ON pl.post_id = ap.id
        WHERE ap.artist_id=%s
    """, (artist_id,))
    likes = cursor.fetchone()['total_likes']

    # Total fan letters
    cursor.execute("""
        SELECT COUNT(*) AS total_letters
        FROM fan_letters
        WHERE artist_id=%s
    """, (artist_id,))
    letters = cursor.fetchone()['total_letters']

    stats = {
        "posts": posts,
        "likes": likes,
        "letters": letters
    }

    return render_template(
        "artist_profile.html",
        artist=artist,
        stats=stats
    )
#-----------artsits=-------------
@artist_auth.route('/artist/<int:artist_id>')
def view_artist_profile(artist_id):

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Artist details
    cursor.execute("SELECT * FROM artists WHERE id=%s", (artist_id,))
    artist = cursor.fetchone()

    if not artist:
        return "Artist not found"

    # Artist posts
    cursor.execute("""
        SELECT * FROM artist_posts
        WHERE artist_id=%s
        ORDER BY created_at DESC
    """, (artist_id,))
    posts = cursor.fetchall()

    # Followers count
    cursor.execute("""
        SELECT COUNT(*) AS followers
        FROM follows
        WHERE artist_id=%s
    """, (artist_id,))
    followers = cursor.fetchone()['followers']

    # Post count
    cursor.execute("""
        SELECT COUNT(*) AS post_count
        FROM artist_posts
        WHERE artist_id=%s
    """, (artist_id,))
    post_count = cursor.fetchone()['post_count']

    return render_template(
        "artist_profile_view.html",
        artist=artist,
        posts=posts,
        followers=followers,
        post_count=post_count
    )
#--------------------gnew route---------------
@artist_auth.route('/start_live')
def start_live():

    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.artist_login'))

    artist_id = session['artist_id']

    cursor = mysql.connection.cursor()

    cursor.execute("""
        UPDATE artist_live
        SET is_live = 1,
            started_at = NOW()
        WHERE artist_id = %s
    """, (artist_id,))

    mysql.connection.commit()

    return render_template("artist_live.html")
#-----------stop live---------------
@artist_auth.route('/stop_live', methods=['POST'])
def stop_live():

    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.artist_login'))

    artist_id = session['artist_id']

    cursor = mysql.connection.cursor()

    cursor.execute("""
        UPDATE artist_live
        SET is_live = 0
        WHERE artist_id = %s
    """, (artist_id,))

    mysql.connection.commit()

    return redirect(url_for('artist_auth.dashboard'))
# ================= LOGOUT =================
@artist_auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('artist_auth.login'))

#--------artist coemnt-------
@artist_auth.route('/artist_comment/<int:post_id>', methods=['POST'])
def artist_comment(post_id):

    if not session.get('artist_id'):
        return redirect(url_for('auth.artist_login'))

    artist_id = session['artist_id']
    comment = request.form['comment']

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        INSERT INTO post_comments (post_id, user_id, role, comment)
        VALUES (%s,%s,'artist',%s)
    """, (post_id, artist_id, comment))

    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('artist_routes.artist_dashboard'))


#-----------------post creation---------------
import os
from flask import request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from models.db import mysql

ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif','mp4'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

@artist_auth.route('/create_post', methods=['POST'])
def create_post():
    if 'artist_id' not in session:
        flash("Please login first.", "danger")
        return redirect(url_for('artist_auth.login'))

    content = request.form.get('content', '').strip()
    if not content:
        flash("Post content cannot be empty!", "danger")
        return redirect(url_for('artist_auth.feed'))

    file = request.files.get('media_file')
    filename = None

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_path = os.path.join(current_app.root_path, 'static/uploads', filename)
        file.save(upload_path)

    # Insert into DB including artist_name
    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO artist_posts (artist_id, artist_name, content, media_filename, created_at) "
        "VALUES (%s, %s, %s, %s, NOW())",
        (session['artist_id'], session['artist_name'], content, filename)
    )
    mysql.connection.commit()
    cur.close()

    flash("Post created successfully!", "success")
    return redirect(url_for('artist_auth.feed'))

#------------------edit profile----------------
from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import os
import MySQLdb.cursors
@artist_auth.route('/edit_profile', methods=['GET','POST'])
def edit_profile():

    if 'artist_id' not in session:
        return redirect(url_for('artist_auth.login'))

    artist_id = session['artist_id']
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ---------------- UPDATE PROFILE ----------------
    if request.method == 'POST':

        name = request.form.get('name')
        full_name = request.form.get('full_name')
        bio = request.form.get('bio')
        phone = request.form.get('phone')

        profile_pic = None

        # -------- PROFILE IMAGE UPLOAD --------
        if 'profile_pic' in request.files:

            file = request.files['profile_pic']

            if file.filename != "":
                filename = secure_filename(file.filename)

                upload_folder = os.path.join('static','uploads')
                filepath = os.path.join(upload_folder, filename)

                file.save(filepath)

                profile_pic = filename

        # -------- UPDATE DATABASE --------

        if profile_pic:
            cur.execute("""
            UPDATE artists
            SET name=%s, full_name=%s, bio=%s, phone=%s, profile_pic=%s
            WHERE id=%s
            """,(name, full_name, bio, phone, profile_pic, artist_id))

        else:
            cur.execute("""
            UPDATE artists
            SET name=%s, full_name=%s, bio=%s, phone=%s
            WHERE id=%s
            """,(name, full_name, bio, phone, artist_id))

        mysql.connection.commit()

        flash("Profile updated successfully!")

        return redirect(url_for('artist_auth.edit_profile'))


    # ---------------- GET ARTIST DATA ----------------
    cur.execute("SELECT * FROM artists WHERE id=%s",(artist_id,))
    artist = cur.fetchone()


    # ---------------- POSTS COUNT ----------------
    cur.execute("""
    SELECT COUNT(*) AS total
    FROM artist_posts
    WHERE artist_id=%s
    """,(artist_id,))
    posts = cur.fetchone()['total']


    # ---------------- FOLLOWERS COUNT ----------------
    cur.execute("""
    SELECT COUNT(*) AS total
    FROM followers
    WHERE followed_id=%s AND followed_type='artist'
    """,(artist_id,))
    followers = cur.fetchone()['total']


    # ---------------- FOLLOWING COUNT ----------------
    cur.execute("""
    SELECT COUNT(*) AS total
    FROM followers
    WHERE follower_id=%s
    """,(artist_id,))
    following = cur.fetchone()['total']


    stats = {
        "posts": posts,
        "followers": followers,
        "following": following
    }


    return render_template(
        "edit_artist_profile.html",
        artist=artist,
        stats=stats
    )