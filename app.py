from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pymysql

app = Flask(__name__)
app.config['SECRET_KEY'] = '546546azezae'
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# MySQL Database connection
db = pymysql.connect(
    host="localhost",
    user="root",
    password="",
    database="event_management",
    cursorclass=pymysql.cursors.DictCursor
)

@login_manager.user_loader
def load_user(user_id):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            return User(user['id'], user['email'], user['is_admin'])
    return None

class User(UserMixin):
    def __init__(self, id, email, is_admin):
        self.id = id
        self.email = email
        self.is_admin = is_admin

@app.route('/')
def home():
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()
    return render_template('home.html', events=events)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user and bcrypt.check_password_hash(user['password'], password):
                login_user(User(user['id'], user['email'], user['is_admin']))
                return redirect(url_for('home'))
            flash('Login Unsuccessful. Check email and password.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        with db.cursor() as cursor:
            cursor.execute("INSERT INTO users (email, password, is_admin) VALUES (%s, %s, %s)", (email, password, False))
            db.commit()
        flash("Registration successful!", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    with db.cursor() as cursor:
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            slots = int(request.form.get('slots'))
            cursor.execute("INSERT INTO events (title, description, slots) VALUES (%s, %s, %s)", (title, description, slots))
            db.commit()
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()
    return render_template('admin.html', events=events)

@app.route('/admin/delete/<int:event_id>')
@login_required
def delete_event(event_id):
    if current_user.is_admin:
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
            db.commit()
    return redirect(url_for('admin'))

@app.route('/admin/update/<int:event_id>', methods=['GET', 'POST'])
@login_required
def update_event(event_id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            slots = int(request.form.get('slots'))
            cursor.execute("UPDATE events SET title = %s, description = %s, slots = %s WHERE id = %s", 
                           (title, description, slots, event_id))
            db.commit()
            return redirect(url_for('admin'))
    return render_template('update_event.html', event=event)

@app.route('/participate/<int:event_id>', methods=['GET'])
@login_required
def participate(event_id):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()

        if event:
            cursor.execute("SELECT * FROM participations WHERE user_id = %s AND event_id = %s", (current_user.id, event_id))
            participation = cursor.fetchone()

            if participation:
                flash('You have already participated in this event!', 'error')
                return redirect(url_for('home'))

            if event['slots'] > 0:
                cursor.execute("INSERT INTO participations (user_id, event_id) VALUES (%s, %s)", (current_user.id, event_id))
                cursor.execute("UPDATE events SET slots = slots - 1 WHERE id = %s", (event_id,))
                db.commit()
                flash('You have successfully participated in the event!', 'success')
            else:
                flash('This event is full!', 'error')
        else:
            flash('Event not found!', 'error')

        cursor.close()
        return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
