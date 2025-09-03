from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import random
import string
import time
from datetime import datetime, timedelta
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
from os import getenv
from flask_mail import Mail, Message
from sqlalchemy.pool import NullPool

app = Flask(__name__)
app.secret_key = getenv("SECRET_KEY", "hello123")  # Use a strong secret key in production

# Enable Flask-SocketIO with CORS to allow mobile access
socketio = SocketIO(app, cors_allowed_origins="*")

db_url = "postgresql://votinguser:jCjWNVbhrboEPfRAueVohXZdNqJR7kB3@dpg-d2pbkp3e5dus73avlph0-a:5432/votingdb_p5a4"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "poolclass": NullPool
}

# Initializing the database
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'home'


# Model for User (email and role)
class User(UserMixin, db.Model):  # Inherit from UserMixin
    __tablename__ = "users" 
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False)

# Model for Idea (name, scores from judge and audience)
class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    score_judge = db.Column(db.Integer, default=0)
    score_audience = db.Column(db.Integer, default=0)
    total_score = db.Column(db.Integer, default=0)

# Model for Events
class Event(db.Model):
    __tablename__ = "events"   # 👈 Add this line
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- OTP SYSTEM ---------------- #
otp_storage = {}

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def is_otp_expired(stored_otp):
    return not stored_otp or time.time() > stored_otp["expiry_time"]

def send_otp_console(email, otp):
    print(f"📩 OTP for {email}: {otp}", flush=True)

# Helper function to calculate total scores
def calculate_total_scores():
    ideas = Idea.query.all()  # Fetch all ideas from the database
    for idea in ideas:
        idea.total_score = idea.score_judge + idea.score_audience
    db.session.commit()  # Commit changes to the database


# Home/Login Page
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        role = request.form['role'].strip().lower()
        user = User.query.filter_by(email=email, role=role).first()
        if user:
            login_user(user)
            session.permanent = True # Keep user logged in
            session["role"] = user.role
            session["user"] = email 
            return redirect(url_for(f'{role}_dashboard'))
        flash("Invalid email or role.", "danger")
    return render_template('login.html')

# Route for sending OTP
@app.route('/send_otp', methods=['POST'])
def send_otp():
    email = request.form["email"].strip().lower()
    role = request.form["role"].strip().lower()

    # Restrict email to @amdocs.com only
    if not email.endswith('@amdocs.com'):
        flash("Only @amdocs.com email addresses are allowed!", "danger")
        return redirect(url_for('home'))
    
    user = User.query.filter_by(email=email , role=role).first()
    
    if role in ["judge", "admin"]:  # Judges and Admins must be registered
        if not user:
            flash("Email not registered!", "danger")
            return redirect(url_for('home'))
        if user.role != role:
            flash("Role mismatch. Please choose the correct role.", "danger")
            return redirect(url_for('home'))
    
    # Allow anyone to log in as audience
    if role == "audience" and not user:
        user = User(email=email, role=role)
        db.session.add(user)
        db.session.commit()

    # Generate and store OTP
    otp = generate_otp()
    expiry_time = time.time() + 900  # 15 minutes from now
    otp_storage[email] = {"otp": otp, "expiry_time": expiry_time, "role": role}

    # Console print instead of email
    send_otp_console(email, otp)  
    flash(f"OTP generated for {email}. Please check your console.", "success")
    return redirect(url_for("otp_verification", email=email))

 
# Route for OTP verification (Fix: Proper redirection based on role)
@app.route('/otp_verification', methods=['GET', 'POST'])
def otp_verification():
    email = request.args.get('email')  # Get email from query string
    print(f"Email from request: {email}")  # Debugging  

    if request.method == 'POST':
        entered_otp = request.form['otp']
        stored_otp = otp_storage.get(email, None)
       

        if not stored_otp:
            flash("No OTP found for this email. Please request a new one.", "danger")
            return redirect(url_for('home'))

        # Check if OTP is expired
        if is_otp_expired(stored_otp):
            flash("OTP has expired. Please request a new one.", "danger")
            del otp_storage[email]  # Remove expired OTP
            return redirect(url_for('home'))

        # Check if entered OTP matches stored OTP
        if entered_otp == stored_otp['otp']:
            role = stored_otp["role"]  
            del otp_storage[email]  # Delete OTP after successful verification

            user = User.query.filter_by(email=email, role = role).first()

            if user:
                session['role'] = user.role  # Store role in session
                session['user'] = email      # Store email in session
                session.permanent = True     # Keep session alive
                login_user(user)             # Ensures user stays logged in

                print(f"User {email} logged in with role {user.role}")  # Debugging

                #Role-based redirection
                if user.role == "admin":
                    return redirect(url_for('dashboard'))
                elif user.role == "judge":
                    return redirect(url_for('events'))
                elif user.role == "audience":
                    return redirect(url_for('events'))
                else:
                    return redirect(url_for('home'))

            else:
                flash("User not found. Please try again.", "danger")
                return redirect(url_for('home'))

        else:
            flash("Invalid OTP. Please try again.", "danger")
            print("Invalid OTP entered!")  # Debugging  
            return redirect(url_for('otp_verification', email=email))

    return render_template('otp_verification.html', email=email)


# Fix in Login Route (Ensuring Users are Stored Correctly)
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email'].strip().lower()
    role = request.form['role'].strip().lower()
      # Ensure only @amdocs.com emails can log in
    if not email.endswith('@amdocs.com'):
        flash("Only @amdocs.com email addresses are allowed!", "danger")
        return redirect(url_for('home'))
    
    user = User.query.filter_by(email=email, role=role).first()

    if not user:
        user = User(email=email, role=role)
        db.session.add(user)
        db.session.commit()  # Commit new user

    if user:
        login_user(user)
        session.permanent = True  # Keep session active
        session['role'] = user.role  # Store role
        session['user'] = email  # Store email
        return redirect(url_for(f'{role}_dashboard'))  
    else:
        flash("Invalid email or role!", "danger")
        return redirect(url_for('home'))

#
@app.route('/dashboard')
@login_required
def dashboard():
    events = Event.query.all()
    ideas = Idea.query.all()

    # Winner calculation
    winner = max(ideas, key=lambda idea: idea.total_score, default=None)

    return render_template(
        'dashboard.html',
        role=current_user.role,
        events=events,
        ideas=ideas,
        winner=winner
    )


#Event List Page (common for all roles)
@app.route('/events')
@login_required
def events():
    events = Event.query.all()
    return render_template('events.html', events=events, role=current_user.role)

#Set Active Event (Admin only)
@app.route('/set_active/<int:event_id>')
@login_required
def set_active(event_id):
    if current_user.role != 'admin':
        return redirect(url_for('home'))
    
    # Deactivate all events first
    Event.query.update({Event.is_active: False})
    
    # Activate selected event
    event = Event.query.get(event_id)
    if event:
        event.is_active = True
        db.session.commit()
    
    flash(f"Event '{event.name}' is now active!", "success")
    return redirect(url_for('events'))


#Redirect After Choosing Active Event
@app.route('/join_event/<int:event_id>')
@login_required
def join_event(event_id):
    event = Event.query.get(event_id)
    if not event or not event.is_active:
        flash("This event is not active!", "danger")
        return redirect(url_for('events'))

    if current_user.role == 'judge':
        return redirect(url_for('judge_dashboard'))
    elif current_user.role == 'audience':
        return redirect(url_for('audience_dashboard'))
    elif current_user.role == 'admin':
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('home'))



# Judge Dashboard
@app.route('/judge_dashboard', methods=['GET', 'POST'])
@login_required
def judge_dashboard():
    if current_user.role != 'judge':
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        for idea in Idea.query.all():
            score = request.form.get(f"score_{idea.id}")
            if score:
                idea.score_judge += int(score)  
                idea.total_score += int(score)
        db.session.commit()
        update_scores()
        return redirect(url_for('thankyou'))  # Redirect after voting
    return render_template('judge_dashboard.html', ideas=Idea.query.all())

# Audience Dashboard
@app.route('/audience_dashboard', methods=['GET', 'POST'])
@login_required
def audience_dashboard():
    if current_user.role != 'audience':
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        for idea in Idea.query.all():
            score = request.form.get(f"score_{idea.id}")
            if score:
                idea.score_audience += int(score) 
                idea.total_score += int(score)
        db.session.commit()
        update_scores()
        return redirect(url_for('thankyou'))  # Redirect after voting
    return render_template('audience_dashboard.html', ideas=Idea.query.all())


# Real-time Score Update Function
def update_scores():
    ideas = Idea.query.all()

    # Create scores dictionary
    scores = {idea.id: {
        'judge': idea.score_judge,
        'audience': idea.score_audience,
        'total': idea.total_score,
        'name': idea.name
    } for idea in ideas}

    # Find the idea with the highest total score (Winner)
    winner = max(ideas, key=lambda idea: idea.total_score, default=None)
    winner_data = {'name': winner.name, 'score': winner.total_score} if winner else None

    # Emit updated scores AND the winner to all connected clients
    socketio.emit('update_scores', {'scores': scores, 'winner': winner_data})


# Admin Dashboard
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('home'))

    ideas = Idea.query.all()

    # Find the idea with the highest total_score
    winner = max(ideas, key=lambda idea: idea.total_score, default=None)

    return render_template('admin_dashboard.html', ideas=ideas, winner=winner)

# Route for result page
@app.route('/result')
def result():
    calculate_total_scores()  # Update total scores for each idea
    return render_template('result.html', total_scores=Idea.query.all())

# Route for Thank You page
@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')



# Logout
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


# Event to Update Scores
@socketio.on('submit_scores')
def handle_score_submission(data):
    for idea_id, score in data.items():
        idea = Idea.query.get(int(idea_id))
        if idea:
            if current_user.role == 'judge':
                idea.score_judge += int(score)
            elif current_user.role == 'audience':
                idea.score_audience += int(score)
            idea.total_score = idea.score_judge + idea.score_audience
        db.session.commit()

    # Call update_scores() to emit updated scores and winner in real time
    update_scores()



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="0.0.0.0", port=int(getenv("PORT", 5000)), debug=True)

