@post.route('/fan_letters', methods=['GET', 'POST'])
def send_fan_letter():
    if 'user_id' not in session:
        flash("Login to send a fan letter", "warning")
        return redirect(url_for('auth.login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Handle sending fan letter
    if request.method == 'POST':
        artist_name = request.form.get('artist_name')
        message = request.form.get('message')

        if not artist_name or not message:
            flash("Artist name and message are required!", "danger")
            return redirect(url_for('post.send_fan_letter'))

        cur.execute(
            "INSERT INTO fan_letters (user_id, artist_name, message, sent_at) VALUES (%s,%s,%s,NOW())",
            (session['user_id'], artist_name, message)
        )
        mysql.connection.commit()
        cur.close()
        flash("Fan letter sent!", "success")
        return redirect(url_for('post.send_fan_letter'))

    # Fetch user's sent letters
    cur.execute("""
        SELECT f.id, f.artist_name, f.message, f.sent_at
        FROM fan_letters f
        WHERE f.user_id=%s
        ORDER BY f.id DESC
    """, (session['user_id'],))
    letters = cur.fetchall()
    cur.close()

    return render_template('fan_letters.html', letters=letters)
