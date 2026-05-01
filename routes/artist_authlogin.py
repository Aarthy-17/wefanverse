@artist_auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, name, password FROM artists WHERE email=%s",
            (email,)
        )
        artist = cur.fetchone()
        cur.close()

        if artist and check_password_hash(artist[2], password):
            session['artist_id'] = artist[0]
            session['artist_name'] = artist[1]
            flash("Welcome back, Artist 🎤", "success")
            return redirect(url_for('post.feed'))  # or artist dashboard
        else:
            flash("Invalid artist email or password", "danger")
            return redirect(url_for('artist_auth.login'))

    # ✅ VERY IMPORTANT (GET request)
    return render_template('artist_login.html')
