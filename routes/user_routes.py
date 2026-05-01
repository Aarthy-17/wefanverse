from flask import (
    Blueprint, render_template, session,
    redirect, request, url_for, flash, jsonify,
    current_app
)
from models.db import mysql
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
import os
import MySQLdb.cursors

user_routes = Blueprint('user_routes', __name__, url_prefix='/user')


# ---------------- AUTH GUARD ----------------
def login_required():
    return bool(session.get('user_id'))


#---------------- DASHBOARD ----------------
@user_routes.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # -------------------------
    # USER INFO
    # -------------------------
    cursor.execute("SELECT username, profile_pic FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    # -------------------------
    # STATS
    # -------------------------

    # Posts count
    cursor.execute("SELECT COUNT(*) AS total FROM posts WHERE user_id=%s", (user_id,))
    posts_count = cursor.fetchone()['total']

    # Followers
    cursor.execute("SELECT COUNT(*) AS total FROM followers WHERE followed_id=%s", (user_id,))
    followers_count = cursor.fetchone()['total']

    # Following
    cursor.execute("SELECT COUNT(*) AS total FROM followers WHERE follower_id=%s", (user_id,))
    following_count = cursor.fetchone()['total']

    # Total Likes Received
    cursor.execute("""
    SELECT COUNT(*) AS total
    FROM likes l
    JOIN posts p ON l.post_id = p.id
    WHERE p.user_id=%s
""", (user_id,))
    total_likes = cursor.fetchone()['total']

    stats = {
        "posts": posts_count,
        "followers": followers_count,
        "following": following_count,
        "likes": total_likes
    }

    # -------------------------
    # USER POSTS
    # -------------------------
    cursor.execute("""
        SELECT 
            p.*,
            (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS like_count,
            (SELECT COUNT(*) FROM post_comments WHERE post_id = p.id) AS comment_count
        FROM posts p
        WHERE p.user_id=%s
        ORDER BY p.created_at DESC
    """, (user_id,))

    posts = cursor.fetchall()

    return render_template(
        "user_dashboard.html",
        posts=posts,
        stats=stats,
        user=user
    )
# ---------------- PROFILE ----------------
@user_routes.route('/profile/<int:user_id>')
def profile_page(user_id):
    if not login_required():
        return redirect(url_for('auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return "User not found", 404

        cursor.execute("""
            SELECT
                COUNT(*) AS posts,
                (SELECT COUNT(*) FROM followers WHERE followed_id=%s) AS followers,
                (SELECT COUNT(*) FROM followers WHERE follower_id=%s) AS following
            FROM posts WHERE user_id=%s
        """, (user_id, user_id, user_id))

        stats = cursor.fetchone()

    finally:
        cursor.close()

    return render_template('profile.html', user=user, stats=stats)


# ---------------- EDIT PROFILE ----------------
@user_routes.route('/edit_profile/<int:user_id>', methods=['GET', 'POST'])
def edit_profile(user_id):
    if not login_required():
        return redirect(url_for('auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        return "User not found", 404

    if request.method == 'POST':
        bio = request.form.get('bio')
        profile_pic = request.files.get('profile_pic')
        filename = user['profile_pic']

        if profile_pic and profile_pic.filename != '':
            filename = secure_filename(profile_pic.filename)
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')

            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            profile_pic.save(os.path.join(upload_folder, filename))

        cursor.execute("""
            UPDATE users
            SET bio=%s, profile_pic=%s
            WHERE id=%s
        """, (bio, filename, user_id))

        mysql.connection.commit()
        cursor.close()

        return redirect(url_for('user_routes.profile_page', user_id=user_id))

    cursor.close()
    return render_template('edit_profile.html', user=user)


# ---------------- FEED ----------------
@user_routes.route('/feed')
def feed_page():

    if not login_required():
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        # ---------------- USER INFO ----------------
        cursor.execute("SELECT username FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()

        # ---------------- STATS ----------------
        stats = {}

        cursor.execute("SELECT COUNT(*) AS c FROM posts WHERE user_id=%s", (user_id,))
        stats['posts'] = cursor.fetchone()['c']

        cursor.execute("SELECT COUNT(*) AS c FROM followers WHERE followed_id=%s", (user_id,))
        stats['followers'] = cursor.fetchone()['c']

        cursor.execute("SELECT COUNT(*) AS c FROM followers WHERE follower_id=%s", (user_id,))
        stats['following'] = cursor.fetchone()['c']


        # ---------------- USER POSTS ----------------
        cursor.execute("""
            SELECT 
                p.id,
                p.user_id,
                p.content,
                p.media_filename,
                p.media_type,
                p.created_at,
                u.username,
                p.is_ad,
                (SELECT COUNT(*) FROM likes WHERE post_id=p.id) AS like_count,
                (SELECT COUNT(*) FROM post_comments WHERE post_id=p.id) AS comment_count
            FROM posts p
            JOIN users u ON p.user_id = u.id
        """)
        user_posts = cursor.fetchall()


        # ---------------- ARTIST POSTS ----------------
        cursor.execute("""
            SELECT 
                id,
                artist_id AS user_id,
                artist_name AS username,
                content,
                media_filename,
                'image' AS media_type,
                created_at,
                is_ad,
                0 AS like_count,
                0 AS comment_count
            FROM artist_posts
        """)
        artist_posts = cursor.fetchall()


        # ---------------- MERGE POSTS ----------------
        posts = user_posts + artist_posts


        # ---------------- SORT BY TIME ----------------
        posts = sorted(posts, key=lambda x: x['created_at'], reverse=True)


        # ---------------- COMMENTS ONLY FOR USER POSTS ----------------
        for post in posts:

            if 'user_id' in post:

                cursor.execute("""
                    SELECT pc.comment, u.username
                    FROM post_comments pc
                    JOIN users u ON pc.user_id = u.id
                    WHERE pc.post_id=%s
                    ORDER BY pc.created_at DESC
                """, (post['id'],))

                post['comments'] = cursor.fetchall()

            else:
                post['comments'] = []

    finally:
        cursor.close()

    return render_template(
        "feed.html",
        posts=posts,
        stats=stats,
        user=user
    )
# ---------------- FEED ----------------
# ---------------- MESSAGES ----------------
@user_routes.route('/messages')
def messages_page():
    if not login_required():
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ---------------- USER CHATS ----------------
    cursor.execute("""
        SELECT u.id,
               u.username AS name,
               u.profile_pic,
               m.message AS last_message,
               m.id AS last_msg_id
        FROM users u
        JOIN messages m
            ON ((m.sender_id = u.id AND m.receiver_id = %s)
             OR (m.receiver_id = u.id AND m.sender_id = %s))
        WHERE m.id = (
            SELECT MAX(id)
            FROM messages
            WHERE ((sender_id = %s AND receiver_id = u.id)
                OR (sender_id = u.id AND receiver_id = %s))
        )
    """, (user_id, user_id, user_id, user_id))

    user_chats = list(cursor.fetchall())

    for chat in user_chats:
        chat['is_artist'] = False
        if not chat.get('profile_pic'):
            chat['profile_pic'] = 'user_icon.png'


    # ---------------- ARTIST CHATS ----------------
    cursor.execute("""
        SELECT a.id,
               a.name,
               a.profile_pic,
               m.message AS last_message,
               m.id AS last_msg_id
        FROM artists a
        JOIN messages m
            ON ((m.sender_id = a.id AND m.receiver_id = %s)
             OR (m.receiver_id = a.id AND m.sender_id = %s))
        WHERE m.id = (
            SELECT MAX(id)
            FROM messages
            WHERE ((sender_id = %s AND receiver_id = a.id)
                OR (sender_id = a.id AND receiver_id = %s))
        )
    """, (user_id, user_id, user_id, user_id))

    artist_chats = list(cursor.fetchall())

    for chat in artist_chats:
        chat['is_artist'] = True
        if not chat.get('profile_pic'):
            chat['profile_pic'] = 'artist_icon.png'


    # ---------------- COMBINE + SORT ----------------
    chats = user_chats + artist_chats
    chats.sort(key=lambda x: x['last_msg_id'], reverse=True)


    # ---------------- SUGGESTED ARTISTS ----------------
    cursor.execute("SELECT id, name, profile_pic FROM artists")
    suggested_artists = list(cursor.fetchall())

    for artist in suggested_artists:

        # Count followers
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM followers WHERE followed_id=%s",
            (artist['id'],)
        )
        artist['followers_count'] = cursor.fetchone()['cnt']

        # Check following
        cursor.execute(
            "SELECT 1 FROM followers WHERE follower_id=%s AND followed_id=%s",
            (user_id, artist['id'])
        )
        artist['is_following'] = bool(cursor.fetchone())

        if not artist.get('profile_pic'):
            artist['profile_pic'] = 'artist_icon.png'

    cursor.close()

    return render_template(
        "messages.html",
        chats=chats,
        suggested_artists=suggested_artists
    )


# ---------------- CHAT ----------------
@user_routes.route('/messages/<int:other_user_id>', methods=['GET', 'POST'])
def chat_page(other_user_id):
    if not login_required():
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ---------------- SEND MESSAGE ----------------
    if request.method == "POST":
        message = request.form.get("message")

        if message and message.strip() != "":
            cursor.execute("""
                INSERT INTO messages (sender_id, receiver_id, message)
                VALUES (%s, %s, %s)
            """, (user_id, other_user_id, message.strip()))

            mysql.connection.commit()

        return redirect(url_for('user_routes.chat_page', other_user_id=other_user_id))


    # ---------------- FETCH CHAT MESSAGES ----------------
    cursor.execute("""
        SELECT id,
               sender_id,
               receiver_id,
               message,
               created_at
        FROM messages
        WHERE (sender_id = %s AND receiver_id = %s)
           OR (sender_id = %s AND receiver_id = %s)
        ORDER BY id ASC
    """, (user_id, other_user_id, other_user_id, user_id))

    messages = list(cursor.fetchall())


    # ---------------- DETERMINE USER OR ARTIST ----------------
    cursor.execute("""
        SELECT id, username AS name, profile_pic
        FROM users
        WHERE id = %s
    """, (other_user_id,))

    other_user = cursor.fetchone()
    is_artist = False

    if not other_user:
        cursor.execute("""
            SELECT id, name, profile_pic
            FROM artists
            WHERE id = %s
        """, (other_user_id,))

        other_user = cursor.fetchone()
        is_artist = True

    if not other_user:
        flash("User or artist not found.", "danger")
        return redirect(url_for("user_routes.messages_page"))

    # ---------------- DEFAULT PROFILE PIC ----------------
    if not other_user.get('profile_pic'):
        other_user['profile_pic'] = (
            'artist_icon.png' if is_artist else 'user_icon.png'
        )

    cursor.close()

    return render_template(
        "chat.html",
        messages=messages,
        other_user=other_user,
        is_artist=is_artist,
        user_id=user_id
    )
#----------serach------------
@user_routes.route('/search')
def search():
    if not login_required():
        return redirect(url_for('auth.login'))

    query = request.args.get('q', '').strip()
    user_id = session['user_id']

    if not query:
        return jsonify({"results": []})

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    results = []

    # Search users
    cursor.execute("""
        SELECT id, username AS name, profile_pic
        FROM users
        WHERE username LIKE %s AND id != %s
        LIMIT 5
    """, (f"%{query}%", user_id))
    users = cursor.fetchall()
    for u in users:
        results.append({
            "id": u['id'],
            "name": u['name'],
            "type": "user",
            "profile_pic": u.get('profile_pic') or 'user_icon.png'
        })

    # Search artists
    cursor.execute("""
        SELECT id, name, profile_pic
        FROM artists
        WHERE name LIKE %s
        LIMIT 5
    """, (f"%{query}%",))
    artists = cursor.fetchall()
    for a in artists:
        results.append({
            "id": a['id'],
            "name": a['name'],
            "type": "artist",
            "profile_pic": a.get('profile_pic') or 'artist_icon.png'
        })

    cursor.close()
    return jsonify({"results": results})

# ---------------- SETTINGS ----------------
@user_routes.route('/settings')
def settings_page():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    return render_template('settings.html')


# ---------------- FORGOT PASSWORD ----------------
@user_routes.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        new_password = generate_password_hash(request.form['new_password'])

        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE users SET password=%s WHERE email=%s", (new_password, email))
        mysql.connection.commit()
        cursor.close()

        flash("Password updated successfully!", "success")
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


# ---------------- FAN LETTERS ----------------
@user_routes.route('/fan_letters')
def fan_letters_page():
    if not login_required():
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        cursor.execute("""
            SELECT id, artist_name, message, sent_at
            FROM fan_letters
            WHERE user_id=%s
            ORDER BY sent_at DESC
        """, (user_id,))
        fan_letters = cursor.fetchall()

        # --- Compute sentiment for each letter ---
        def analyze_sentiment(text):
            text = text.lower()
            positive_words = ['love','amazing','great','awesome','happy','excited','legend','best']
            negative_words = ['hate','bad','worst','boring','disappointed','angry','sad']

            pos = sum(word in text for word in positive_words)
            neg = sum(word in text for word in negative_words)

            if pos > neg:
                return 'Positive'
            elif neg > pos:
                return 'Negative'
            return 'Neutral'

        for letter in fan_letters:
            letter['sentiment'] = analyze_sentiment(letter['message'])

    finally:
        cursor.close()

    return render_template('fan_letters.html', letters=fan_letters)


# ---------------- BOOST POST ----------------
@user_routes.route('/boost/<int:post_id>', methods=['POST'])
def boost_post(post_id):
    if not login_required():
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    budget = request.form.get('budget')

    if not budget:
        flash("Budget required", "danger")
        return redirect(url_for('user_routes.feed_page'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        cursor.execute("SELECT * FROM posts WHERE id=%s AND user_id=%s", (post_id, user_id))
        post = cursor.fetchone()

        if not post:
            flash("Unauthorized", "danger")
            return redirect(url_for('user_routes.feed_page'))

        cursor.execute("""
            UPDATE posts
            SET is_ad=1,
                ad_budget=%s,
                ad_start=NOW(),
                ad_end=DATE_ADD(NOW(), INTERVAL 3 DAY)
            WHERE id=%s
        """, (budget, post_id))

        mysql.connection.commit()
    finally:
        cursor.close()

    flash("Post boosted successfully 🚀", "success")
    return redirect(url_for('user_routes.feed_page'))


# ---------------- ACCOUNT CENTER ----------------
@user_routes.route('/settings/account-center')
def account_center():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    return render_template('account_center.html')


# ---------------- PERSONAL DETAILS ----------------
@user_routes.route('/settings/account-center/personal-details', methods=['GET', 'POST'])
def personal_details():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')

        cursor.execute("""
            UPDATE users
            SET full_name=%s, email=%s, phone=%s
            WHERE id=%s
        """, (full_name, email, phone, user_id))
        mysql.connection.commit()
        flash("Personal details updated successfully 💜", "success")

    cursor.execute("SELECT full_name, email, phone FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    cursor.close()

    return render_template('personal_details.html', user=user)


# ---------------- PASSWORD SECURITY ----------------
from werkzeug.security import check_password_hash, generate_password_hash

@user_routes.route('/settings/account-center/password-security', methods=['GET', 'POST'])
def password_security():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    message = None

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Fetch current password from DB
        cursor.execute("SELECT password FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()

        if not user:
            message = "User not found."
        elif new_password != confirm_password:
            message = "New password and confirm password do not match."
        elif not check_password_hash(user['password'], current_password):
            message = "Current password is incorrect."
        else:
            # Update password
            hashed_new = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password=%s WHERE id=%s", (hashed_new, user_id))
            mysql.connection.commit()
            message = "Password updated successfully 💜"

    cursor.close()
    return render_template(
        'password_security.html',
        active_page='password_security',
        message=message
    )


# ---------------- TWO-FACTOR AUTH ----------------
@user_routes.route('/settings/account-center/two-factor', methods=['GET', 'POST'])
def two_factor():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    message = None

    if request.method == 'POST':
        enable_2fa = request.form.get('enable_2fa')  # checkbox returns 'on' if checked
        contact = request.form.get('phone_or_email', '').strip()

        # Convert checkbox to boolean
        enable_2fa = True if enable_2fa == 'on' else False

        # Validation
        if enable_2fa and not contact:
            message = "Please provide a phone number or email to enable 2FA."
        else:
            # Update 2FA settings in DB
            cursor.execute("""
                UPDATE users
                SET two_factor_enabled=%s, two_factor_contact=%s
                WHERE id=%s
            """, (enable_2fa, contact if enable_2fa else None, user_id))
            mysql.connection.commit()

            if enable_2fa:
                message = "Two-Factor Authentication enabled successfully 💜"
            else:
                message = "Two-Factor Authentication disabled 💜"

    # Fetch current 2FA status
    cursor.execute("""
        SELECT two_factor_enabled, two_factor_contact
        FROM users
        WHERE id=%s
    """, (user_id,))
    user_2fa = cursor.fetchone()
    cursor.close()

    return render_template(
        'two_factor.html',
        active_page='two_factor',
        message=message,
        user_2fa=user_2fa
    )
# ---------------- NOTIFICATIONS PAGE ----------------
# ---------------- NOTIFICATIONS PAGE ----------------
@user_routes.route('/notifications')
def notifications_page():

    if not login_required():
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        cursor.execute("""
            SELECT id, type, message, created_at
            FROM notifications
            WHERE user_id=%s
            ORDER BY created_at DESC
        """, (user_id,))

        notifications = cursor.fetchall()

    finally:
        cursor.close()

    return render_template('notifications.html', notifications=notifications)
# ---------------- PRIVACY SETTINGS ----------------

@user_routes.route('/privacy_settings', methods=['GET', 'POST'])
def privacy_settings():

    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        try:
            # ✅ Handle Private Toggle
            is_private = 1 if request.form.get('private_account') else 0

            cursor.execute("""
                UPDATE users
                SET is_private = %s
                WHERE id = %s
            """, (is_private, user_id))

            # ✅ Handle Profile Photo Upload
            if 'profile_photo' in request.files:
                file = request.files['profile_photo']

                if file and file.filename != '':
                    filename = secure_filename(file.filename)

                    upload_path = os.path.join(
                        current_app.config['UPLOAD_FOLDER'], filename
                    )

                    file.save(upload_path)

                    cursor.execute("""
                        UPDATE users
                        SET profile_pic = %s
                        WHERE id = %s
                    """, (filename, user_id))

            mysql.connection.commit()
            flash("Privacy settings updated successfully!", "success")

        except Exception as e:
            print("Error:", e)
            flash("Something went wrong!", "danger")

        return redirect(url_for('user_routes.privacy_settings'))

    # ✅ Fetch Current Data
    cursor.execute("""
        SELECT is_private, profile_pic
        FROM users
        WHERE id = %s
    """, (user_id,))

    privacy = cursor.fetchone()
    cursor.close()

    return render_template("privacy_settings.html", privacy=privacy)
#---------------------message_controls------------------------------
@user_routes.route('/message_controls')
def message_controls():
    # Example: fetch user settings from DB (optional)
    user_settings = {
        "can_message": "Everyone",
        "can_add_groups": "Friends",
        "message_requests": "Off"
    }
    return render_template('message_controls.html', settings=user_settings)

@user_routes.route('/settings/ads')
def ads_settings():
    # Example: fetch user settings from DB (optional)
    ads_settings = {
        "ad_interests": "On",
        "data_from_partners": "On",
        "activity_information": "Off"
    }
    return render_template('settings_ads.html', ads_settings=ads_settings)

@user_routes.route('/settings/security')
def security_settings():
    # Example: fetch security-related data if needed
    security_info = {
        "two_factor": "Off",
        "login_activity": "Recent logins available"
    }
    return render_template('settings_security.html', security=security_info)

# ---------------- ADS INTERESTS ----------------
@user_routes.route('/ad-interests', methods=['GET', 'POST'])
def ads_interests():
    if not login_required():
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ------------------ Save user preferences ------------------
    if request.method == 'POST':
        interests = {
            'music': 1 if request.form.get('music') else 0,
            'fashion': 1 if request.form.get('fashion') else 0,
            'movies': 1 if request.form.get('movies') else 0,
        }
        for key, value in interests.items():
            cursor.execute(
                "UPDATE users SET {}=%s WHERE id=%s".format(key),
                (value, user_id)
            )
        mysql.connection.commit()
        flash("✅ Preferences saved successfully!", "success")
        return redirect(url_for('user_routes.ads_interests'))  # reload page to show flash

    # ------------------ Fetch boosted posts / ads ------------------
    cursor.execute("""
        SELECT a.id AS artist_id, a.name AS artist_name, a.profile_pic,
               p.id AS post_id, p.title, p.content, p.media_filename, p.media_type, p.created_at
        FROM artists a
        JOIN posts p ON a.id = p.user_id
        WHERE p.is_ad = 1
        ORDER BY p.ad_start DESC
        LIMIT 10
    """)
    boosted_posts = cursor.fetchall()
    cursor.close()

    return render_template("ads_interests.html", boosted_posts=boosted_posts)


# ---------------- ADS DATA PARTNERS ----------------
@user_routes.route('/ads_data_partners', methods=['GET', 'POST'])
def ads_data_partners():

    if request.method == 'POST':
        partner_data = 'partner_data' in request.form

        # Save to DB here if needed

        flash("Settings updated successfully!", "success")
        return redirect(url_for('user_routes.ads_data_partners'))

    return render_template('ads_data_partners.html')


# ---------------- ADS ACTIVITY INFO ---------------

from textblob import TextBlob

@user_routes.route('/ads/activity-info', methods=['GET', 'POST'])
def activity_information():

    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # -------- SAVE SETTING --------
    if request.method == 'POST':
        activity_tracking = 1 if 'activity_tracking' in request.form else 0

        cursor.execute("""
            UPDATE users
            SET activity_tracking = %s
            WHERE id = %s
        """, (activity_tracking, user_id))

        mysql.connection.commit()
        flash("Activity settings updated successfully!", "success")
        return redirect(url_for('user_routes.activity_information'))

    # -------- POSTS COUNT --------
    cursor.execute("SELECT content FROM posts WHERE user_id=%s", (user_id,))
    user_posts = cursor.fetchall()

    posts = len(user_posts)

    # -------- FOLLOWERS --------
    cursor.execute("""
        SELECT COUNT(*) AS followers
        FROM followers
        WHERE followed_id=%s AND followed_type='user'
    """, (user_id,))
    followers = cursor.fetchone()['followers'] or 0

    # -------- FOLLOWING --------
    cursor.execute("""
        SELECT COUNT(*) AS following
        FROM followers
        WHERE follower_id=%s AND followed_type='user'
    """, (user_id,))
    following = cursor.fetchone()['following'] or 0

    # -------- SENTIMENT ANALYSIS --------
    positive = 0
    negative = 0
    neutral = 0

    for post in user_posts:
        analysis = TextBlob(post['content'])
        polarity = analysis.sentiment.polarity

        if polarity > 0:
            positive += 1
        elif polarity < 0:
            negative += 1
        else:
            neutral += 1

    return render_template(
        'ads_activity_info.html',
        posts=posts,
        followers=followers,
        following=following,
        positive=positive,
        negative=negative,
        neutral=neutral
    )

#-----------user dashbaord like share cokmment---------

# ---------------- EDIT POST ----------------
@user_routes.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if not login_required():
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        cursor.execute("""
            SELECT * FROM posts
            WHERE id=%s AND user_id=%s
        """, (post_id, user_id))

        post = cursor.fetchone()

        if not post:
            flash("Unauthorized access", "danger")
            return redirect(url_for('user_routes.dashboard'))

        if request.method == 'POST':
            content = request.form.get('content')

            cursor.execute("""
                UPDATE posts
                SET content=%s
                WHERE id=%s
            """, (content, post_id))

            mysql.connection.commit()
            flash("Post updated successfully 💜", "success")
            return redirect(url_for('user_routes.dashboard'))

    finally:
        cursor.close()

    return render_template('edit_post.html', post=post)


# ---------------- DELETE POST ----------------
@user_routes.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if not login_required():
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        cursor.execute("""
            SELECT id FROM posts
            WHERE id=%s AND user_id=%s
        """, (post_id, user_id))

        post = cursor.fetchone()

        if not post:
            flash("Unauthorized action", "danger")
            return redirect(url_for('user_routes.dashboard'))

        # Delete likes first (important if foreign key)
        cursor.execute("DELETE FROM likes WHERE post_id=%s", (post_id,))

        # Delete post
        cursor.execute("DELETE FROM posts WHERE id=%s", (post_id,))

        mysql.connection.commit()

    finally:
        cursor.close()

    flash("Post deleted successfully 🗑", "success")
    return redirect(url_for('user_routes.dashboard'))
#-------------------view post---------------------
@user_routes.route('/post/<int:post_id>')
def view_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get post
    cursor.execute("SELECT * FROM posts WHERE id=%s", (post_id,))
    post = cursor.fetchone()

    # Get comments
    cursor.execute("""
        SELECT pc.*, u.username
        FROM post_comments pc
        JOIN users u ON pc.user_id = u.id
        WHERE pc.post_id=%s
        ORDER BY pc.created_at DESC
    """, (post_id,))
    comments = cursor.fetchall()

    return render_template("view_post.html", post=post, comments=comments)
#---------------dashboard afdd comments---------------------
from textblob import TextBlob
from textblob import TextBlob

@user_routes.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):

    comment = request.form['comment']
    user_id = session['user_id']

    analysis = TextBlob(comment)
    polarity = analysis.sentiment.polarity

    if polarity > 0:
        sentiment = "Positive"
    elif polarity < 0:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    cursor = mysql.connection.cursor()

    cursor.execute("""
        INSERT INTO post_comments (post_id, user_id, comment, sentiment)
        VALUES (%s,%s,%s,%s)
    """,(post_id, user_id, comment, sentiment))

    mysql.connection.commit()

    return redirect(request.referrer)
#-------------------like post---------------------
@user_routes.route('/like_post/<int:post_id>', methods=['POST'])
def like_post(post_id):

    if not session.get('user_id'):
        return jsonify({"success": False})

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        cursor.execute("""
            SELECT id FROM likes
            WHERE user_id=%s AND post_id=%s
        """, (user_id, post_id))

        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                DELETE FROM likes
                WHERE user_id=%s AND post_id=%s
            """, (user_id, post_id))
            liked = False
        else:
            cursor.execute("""
                INSERT INTO likes (user_id, post_id)
                VALUES (%s,%s)
            """, (user_id, post_id))
            liked = True

        mysql.connection.commit()

        # get updated like count
        cursor.execute("SELECT COUNT(*) AS total FROM likes WHERE post_id=%s", (post_id,))
        likes = cursor.fetchone()['total']

    finally:
        cursor.close()

    return jsonify({
        "success": True,
        "liked": liked,
        "likes": likes
    })
#--------------------watch live--------------------
@user_routes.route('/watch_live/<int:artist_id>')
def watch_live(artist_id):

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT name, profile_pic
        FROM artists
        WHERE id = %s
    """,(artist_id,))

    artist = cursor.fetchone()

    return render_template("watch_live.html", artist=artist)
#--------------------notifications--------------------
#---------------user create post-------------------
from textblob import TextBlob

@user_routes.route('/create_post', methods=['POST'])
def create_post():

    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    content = request.form.get('content')
    media = request.files.get('media')

    media_filename = None
    media_type = None

    # -------- SENTIMENT ANALYSIS --------
    text = content.lower()

    positive_words = [
        'happy','love','good','great','awesome',
        'hype','win','won','award','vip','concert','best'
    ]

    negative_words = [
        'sad','bad','hate','worst','angry','terrible'
    ]

    sentiment = "Neutral"

    for word in positive_words:
        if word in text:
            sentiment = "Positive"
            break

    for word in negative_words:
        if word in text:
            sentiment = "Negative"
            break

    # AI fallback
    if sentiment == "Neutral":
        analysis = TextBlob(content)
        polarity = analysis.sentiment.polarity

        if polarity > 0.1:
            sentiment = "Positive"
        elif polarity < -0.1:
            sentiment = "Negative"

    # -------- MEDIA UPLOAD --------
    if media and media.filename != "":
        filename = secure_filename(media.filename)

        upload_path = os.path.join("static", "uploads", filename)
        media.save(upload_path)

        media_filename = filename

        if filename.lower().endswith(('png','jpg','jpeg','gif')):
            media_type = "image"
        elif filename.lower().endswith(('mp4','mov','webm')):
            media_type = "video"

    # -------- INSERT POST --------
    cursor = mysql.connection.cursor()

    cursor.execute("""
    INSERT INTO posts (user_id, content, media_filename, media_type, sentiment)
    VALUES (%s,%s,%s,%s,%s)
    """,(user_id, content, media_filename, media_type, sentiment))

    mysql.connection.commit()

    return redirect(url_for('user_routes.feed_page'))
#-------reactions--------------
@user_routes.route('/react/<int:post_id>/<reaction>')
def react(post_id, reaction):

    user_id = session['user_id']

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO reactions (post_id, user_id, reaction)
        VALUES (%s,%s,%s)
    """,(post_id, user_id, reaction))

    mysql.connection.commit()

    return redirect(request.referrer)

#--------------------report post--------------------
# ---------------- FOLLOW / UNFOLLOW ARTIST ----------------
@user_routes.route('/follow/<int:artist_id>', methods=['POST'])
def follow_artist(artist_id):

    if 'user_id' not in session:
        return jsonify({"error": "login required"}), 401

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        # Check if already following
        cursor.execute("""
            SELECT * FROM followers
            WHERE follower_id=%s AND followed_id=%s
        """, (user_id, artist_id))

        existing = cursor.fetchone()

        if existing:
            # Unfollow
            cursor.execute("""
                DELETE FROM followers
                WHERE follower_id=%s AND followed_id=%s
            """, (user_id, artist_id))
            status = "unfollowed"

        else:
            # Follow
            cursor.execute("""
                INSERT INTO followers (follower_id, followed_id)
                VALUES (%s,%s)
            """, (user_id, artist_id))
            status = "followed"

        mysql.connection.commit()

        # Updated followers count
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM followers
            WHERE followed_id=%s
        """, (artist_id,))

        followers = cursor.fetchone()['total']

    finally:
        cursor.close()

    return jsonify({
        "status": status,
        "followers": followers
    })