from xml.etree import ElementTree
from flask import Flask, render_template, redirect, session, url_for, flash, request
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pymysql
import requests
from smtp import send_confirmation_email,send_participation_email
from dotenv import load_dotenv
import os
import pymysql
import datetime
from werkzeug.utils import secure_filename



load_dotenv()

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')

app.permanent_session_lifetime = datetime.timedelta(minutes=10)  # Set session timeout to 10 minutes


app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
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
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id))
        user = cursor.fetchone()
        if user:
            return User(user['id'], user['email'], user['is_admin'])
    return None

class User(UserMixin):
    def __init__(self, id, email, is_admin):
        self.id = id
        self.email = email
        self.is_admin = is_admin


def get_location_name(longitude, latitude):
    geocodeapi = os.getenv("GEOCODE_API_KEY")
    
    location_apiurl = f"https://geocode.xyz/{latitude},{longitude}?geoit=xml&auth={geocodeapi}"
    location_response = requests.get(location_apiurl)
    

    if location_response.status_code != 200:
        return "Error: Unable to fetch location data"

    try:
        root = ElementTree.fromstring(location_response.text)


        country = root.find(".//countryname")
        country = country.text if country is not None else "Unknown"

        region = root.find(".//region")
        region = region.text if region is not None else "Unknown"

        postal = root.find(".//postal")
        postal = postal.text if postal is not None else "Unknown"

        admin5 = ""
        admin6 = ""

        adminareas = root.findall(".//adminareas")
        for area in adminareas:
            admin5_element = area.find(".//admin5/name_fr")
            admin5 = admin5_element.text if admin5_element is not None else ""

            admin6_element = area.find(".//admin6/name_fr")
            admin6 = admin6_element.text if admin6_element is not None else ""
        
        location_name = f"{country},{region},{admin5},{admin6},{postal}"
        return location_name

    except Exception as e:
        return f"Error: {str(e)}"
    




TICKETTAILOR_EVENT_SERIES_URL = 'https://api.tickettailor.com/v1/events'
API_KEY = os.getenv("TAILOR_TICKET_API_KEY")

headers = {
    'Accept': 'application/json'
}

def get_event_series():
    response = requests.get(TICKETTAILOR_EVENT_SERIES_URL,auth=(API_KEY, ''), headers=headers)
    
    print("Response Status Code:", response.status_code)
    if response.status_code == 200:
        events_data = response.json()
        if events_data['data']:
            print(events_data['data'])  
            return events_data['data']
        else:
            print("No event series found.")
            return []
    else:
        print(f"Error fetching event series: {response.status_code}")
        return []
@app.route('/')
def home():
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) as COUNT_ROWS FROM events")
        count = cursor.fetchone()
        print(count)

    line_count = count['COUNT_ROWS']

    if not events:
        events_api = get_event_series() 
        return render_template('home.html', events_api=events_api, line_count=5)

    for event in events:
        if current_user.is_authenticated:
            with db.cursor() as cursor:
                cursor.execute("SELECT * FROM participations WHERE user_id = %s AND event_id = %s", (current_user.id, event['id']))
                event['participated'] = cursor.fetchone() is not None
        else:
            event['participated'] = False

        location_name = get_location_name(event.get('longitude'), event.get('latitude'))
        event['location_name'] = location_name

    return render_template('home.html', events=events, line_count=line_count)





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
                        user_obj = User(user['id'], user['email'], user['is_admin'])
                        login_user(user_obj)
                        session.permanent = True  
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
            
            cursor.execute("SELECT id FROM users WHERE email = %s", (email))
            user = cursor.fetchone()
            user_id = user['id']

            send_confirmation_email(email, user_id)
        
        flash("Registration successful! Please check your email to activate your account.", "success")
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/activate/<int:user_id>')
def activate_account(user_id):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id))
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

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
            event_date = request.form.get('event_date')
            event_time = request.form.get('event_time')
            latitude = round(float(request.form.get('latitude')), 6)
            longitude = round(float(request.form.get('longitude')), 6)


            image_url = None

            print(request)
            if 'image' in request.files:
                image = request.files['image']
                print("Image:", image)
                if image and allowed_file(image.filename):
                    filename = secure_filename(image.filename)
                    print("Filename:", filename)

                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    image.save(image_path)

                    image_url = f'uploads/{filename}'
                    print("Image URL:", image_url)


            cursor.execute(
                """
                INSERT INTO events (title, description, slots, event_date, event_time, latitude, longitude, image_url) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (title, description, slots, event_date, event_time, latitude, longitude, image_url)
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
            cursor.execute("DELETE FROM events WHERE id = %s", (event_id))
            db.commit()
    return redirect(url_for('admin'))

@app.route('/admin/update/<int:event_id>', methods=['GET', 'POST'])
@login_required
def update_event(event_id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id))
        event = cursor.fetchone()

        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            slots = int(request.form.get('slots'))
            latitude = round(float(request.form.get('latitude')), 6)
            longitude = round(float(request.form.get('longitude')), 6)


            image_url = None

            print(request)
            if 'image' in request.files:
                image = request.files['image']
                print("Image:", image)
                if image and allowed_file(image.filename):
                    filename = secure_filename(image.filename)
                    print("Filename:", filename)

                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    image.save(image_path)


                    image_url = f'uploads/{filename}'
                    print("Image URL:", image_url)

            cursor.execute("""
                UPDATE events 
                SET title = %s, description = %s, slots = %s, latitude = %s, longitude = %s , image_url = %s
                WHERE id = %s
            """, (title, description, slots, latitude, longitude, image_url,event_id))
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
                cursor.execute("UPDATE events SET slots = slots - 1 WHERE id = %s", (event_id))
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

@app.route('/event_weather/<int:event_id>', methods=['GET'])
@login_required
def event_weather(event_id):
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT title, event_date, event_time, latitude, longitude FROM events WHERE id = %s", (event_id,))
            event = cursor.fetchone()

            if event:
                latitude = event['latitude']
                longitude = event['longitude']
                event_date = event['event_date']
                
                if isinstance(event['event_time'], datetime.timedelta):
                    event_time = (datetime.datetime.min + event['event_time']).time()
                else:
                    event_time = event['event_time']
                
                event_datetime = datetime.datetime.combine(event_date, event_time)
                
                local_tz = datetime.datetime.now().astimezone().tzinfo
                event_datetime = event_datetime.replace(tzinfo=local_tz).astimezone(datetime.timezone.utc)

                api_key = '4b18e3234581aa271f81c4ce797cf7f1'
                weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={latitude}&lon={longitude}&appid={api_key}&units=metric"
                response = requests.get(weather_url)
                print("Weather URL:", weather_url)
                print("Response:", response)

                location_name = get_location_name(longitude, latitude)



                if response.status_code != 200:
                    flash('Failed to retrieve weather data.', 'warning')
                    return redirect(url_for('home'))

                data = response.json()
                weather_info = None

                if 'list' in data:
                    print("Forecast data:", data['list'])
                    for forecast in data['list']:
                            weather_info = forecast

                if weather_info:
                    return render_template('event_weather.html', event=event, weather_info=weather_info,event_datetime=event_datetime,location_name=location_name)
                else:
                    flash('No weather info found for this event time.', 'info')
                    return render_template('event_weather.html', event=event, weather_info=None)
            else:
                flash('Event not found or access denied.', 'danger')
                return redirect(url_for('home'))
    except Exception as e:
        print(f"An error occurred: {e}")
        flash('An unexpected error occurred. Please try again later.', 'danger')
        return redirect(url_for('home'))




if __name__ == '__main__':
    app.run(debug=True)
