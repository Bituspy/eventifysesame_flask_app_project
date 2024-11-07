from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pymysql
from smtp import send_confirmation_email,send_participation_email
from dotenv import load_dotenv
import os
import pymysql

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = '546546azezae'
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


db = pymysql.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    cursorclass=pymysql.cursors.DictCursor
)

send_confirmation_email("bituxpie@gmail.com", 3)

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
            if user:
                if user['activated']:
                    if bcrypt.check_password_hash(user['password'], password):
                        login_user(User(user['id'], user['email'], user['is_admin']))
                        return redirect(url_for('home'))
                    flash('Login Unsuccessful. Check email and password.', 'danger')
                else:
                    flash("Your account is not activated yet. Please check your email.", "warning")
            else:
                flash("No user found with this email.", "danger")
    return render_template('login.html')




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (first_name, last_name, email, password, is_admin, activated) VALUES (%s, %s, %s, %s, %s, %s)",
                (first_name, last_name, email, password, False, False)
            )
            db.commit()
            
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            user_id = user['id']

            send_confirmation_email(email, user_id)
        
        flash("Registration successful! Please check your email to activate your account.", "success")
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/activate/<int:user_id>')
def activate_account(user_id):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            cursor.execute("UPDATE users SET activated = %s WHERE id = %s", (True, user_id))
            db.commit()
            flash("Your account has been activated! You can now log in.", "success")
        else:
            flash("Invalid activation link.", "danger")
    
    return redirect(url_for('login'))



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
            latitude = round(float(request.form.get('latitude')), 6)
            longitude = round(float(request.form.get('longitude')), 6)

            
            cursor.execute(
                "INSERT INTO events (title, description, slots, latitude, longitude) VALUES (%s, %s, %s, %s, %s)",
                (title, description, slots, latitude, longitude)
            )
            db.commit()

        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()

        cursor.execute("""
            SELECT p.event_id, u.first_name, u.last_name, p.participation_date
            FROM participations p
            JOIN users u ON p.user_id = u.id
        """)
        participations = cursor.fetchall()

        participations_by_event = {}
        for participation in participations:
            event_id = participation['event_id']
            if event_id not in participations_by_event:
                participations_by_event[event_id] = []
            participations_by_event[event_id].append(
                f"{participation['first_name']} {participation['last_name']} ({participation['participation_date']})"
            )

    return render_template('admin.html', events=events, participations_by_event=participations_by_event)


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
            latitude = round(float(request.form.get('latitude')), 6)
            longitude = round(float(request.form.get('longitude')), 6)

            cursor.execute("""
                UPDATE events 
                SET title = %s, description = %s, slots = %s, latitude = %s, longitude = %s 
                WHERE id = %s
            """, (title, description, slots, latitude, longitude, event_id))
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

                send_participation_email(
                    current_user.email,
                    event_id,
                    event['title'],
                    event['longitude'],
                    event['latitude']
                )

                flash('You have successfully participated in the event!', 'success')
            else:
                flash('This event is full!', 'error')
        else:
            flash('Event not found!', 'error')

        cursor.close()
        return redirect(url_for('home'))



if __name__ == '__main__':
    app.run(debug=True)
