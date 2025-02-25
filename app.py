import pymysql
pymysql.install_as_MySQLdb()

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
import os
import random
import string
import time
from datetime import datetime, timedelta

import smtplib

EMAIL = os.environ.get("MAIL_USERNAME")
PASSWORD = os.environ.get("MAIL_PASSWORD")

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(EMAIL, PASSWORD) 
    #server.login('your_email@gmail.com', 'your_app_password')
    print("✅ SMTP Connection Successful!")
    server.quit()
except Exception as e:
    print(f"❌ SMTP Connection Failed: {e}")


app = Flask(__name__)
app.secret_key = 'hello123'  # Use a strong secret key in production
# 🔹 **Flask-Mail Configuration (Set these values in Render)**
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Change if using another provider
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')  # Set in Render
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')  # Set in Render
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME') or "noreply@example.com"

#app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')
#app.config['MAIL_USERNAME'] = 'ingawalevaishnavi8@gmail.com'
#app.config['MAIL_PASSWORD'] = 'xyzn wxuf atep znqu'  # Use App Password


mail = Mail(app)  # Initialize Flask-Mail

# Configuring SQLAlchemy with MYSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:11111@localhost/voting_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initializing the database
db = SQLAlchemy(app)

# Model for User (email and role)
class User(db.Model):
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

# OTP storage (simulated DB with an array)
otp_storage = []

# Helper function to generate OTP
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))  # Generates a 6-digit OTP

# 🔹 **Function to Send Email using Flask-Mail**
def send_mail(email, subject, message):
    try:
        msg = Message(
            subject=subject,
            recipients=[email],  # Send to any user (Admin, Judge, Audience)
            body=message,
            sender=app.config['MAIL_DEFAULT_SENDER']  # Explicit sender
        )
        mail.send(msg)
        print(f"✅ Email sent successfully to {email}!")
    except Exception as e:
        print(f"❌ Error sending email to {email}: {e}")

@app.route('/test_email/<role>')
def test_email(role):
    user = User.query.filter_by(role=role).first()
    if user:
        send_mail(user.email, f"Test Email for {role}", f"Hello {role}, this is a test email.")
        return f"✅ Test email sent to {user.email}!"
    return "❌ No user found for this role."



# Helper function to calculate total scores
def calculate_total_scores():
    ideas = Idea.query.all()  # Fetch all ideas from the database
    for idea in ideas:
        idea.total_score = idea.score_judge + idea.score_audience
    db.session.commit()  # Commit changes to the database

# Helper function to check if OTP is expired
def is_otp_expired(stored_otp):
    expiration_time = stored_otp['expiry_time']
    return time.time() > expiration_time

# Route for home page (login page)
@app.route('/')
def home():
    return render_template('login.html')

# Route for sending OTP
@app.route('/send_otp', methods=['POST'])
def send_otp():
    email = request.form['email']
    role = request.form['role']
    
    user = User.query.filter_by(email=email).first()
    
    if user:
        if user.role == role:  # Check if the entered role matches the stored role
            otp = generate_otp()
            # Store OTP in the 'otp_storage' list with expiry time (10 minutes)
            expiry_time = time.time() + 600  # 10 minutes from now
            otp_storage.append({"email": email, "otp": otp, "expiry_time": expiry_time})

            # Send OTP via email
           # subject = "Your OTP Code"
           # message = f"Your OTP code is: {otp}"
            #send_mail(email, subject, message)
            print(f"📩 Sending OTP {otp} to {email}")  # Debugging
            send_mail(email, "Your OTP Code", f"Your OTP code is: {otp}")

            flash(f"OTP sent to {email}. Please check your email.", "success")
            return redirect(url_for('otp_verification', email=email))
        else:
            flash("Role mismatch. Please choose the correct role.", "danger")
            return redirect(url_for('home'))
    else:
        flash("Email not registered!", "danger")
        return redirect(url_for('home'))

# Route for OTP verification
@app.route('/otp_verification', methods=['GET', 'POST'])
def otp_verification():
    email = request.args.get('email')  # Get the email from the URL query string
    
    if request.method == 'POST':
        entered_otp = request.form['otp']
        
        # Check if the entered OTP matches the stored OTP for the email
        stored_otp = next((otp for otp in otp_storage if otp['email'] == email), None)
        
        if stored_otp:
            if is_otp_expired(stored_otp):
                flash("OTP has expired. Please request a new one.", "danger")
                return redirect(url_for('home'))
            elif entered_otp == stored_otp['otp']:  # Compare the entered OTP with the stored OTP
                session['user'] = email  # Set the user session
                user = User.query.filter_by(email=email).first()  # Fetch the user object
                if user:
                    role = user.role  # Get the user's role from the database
                    return redirect(url_for(f'{role}_dashboard'))  # Redirect based on user role
                else:
                    flash("User not found. Please try again.", "danger")
                    return redirect(url_for('home'))
            else:
                flash("Invalid OTP. Please try again.", "danger")  # Invalid OTP message
                return redirect(url_for('otp_verification', email=email))  # Redirect to OTP page to try again
        else:
            flash("No OTP found for this email. Please request a new one.", "danger")
            return redirect(url_for('home'))

    return render_template('otp_verification.html', email=email)


# Route for Judge Dashboard
@app.route('/judge_dashboard', methods=['GET', 'POST'])
def judge_dashboard():
    if request.method == 'POST':
        # Process Judge scores (0-50 for each idea)
        for idea in Idea.query.all():
            score = request.form.get(f"score_{idea.id}")
            if score:
               # idea.score_judge = int(score)
               score = int(score)
                # Ensure score is within 0-100 and a multiple of 5
               if 0 <= score <= 100 and score % 5 == 0:
                    idea.score_judge = score
               else:
                    flash(f"Invalid score for Idea {idea.id}. Please enter a multiple of 5 between 0 and 100.", "danger")
                    return redirect(url_for('judge_dashboard'))  # Reload page on error
        db.session.commit()  # Save changes to the database
        flash("Scores submitted successfully! Thank you for your participation.", "success")
        session.pop('user', None)  # Log out the user
        return redirect(url_for('thank_you'))  # Redirect to Thank You page
    return render_template('judge_dashboard.html', ideas=Idea.query.all())

# Route for Audience Dashboard
@app.route('/audience_dashboard', methods=['GET', 'POST'])
def audience_dashboard():
    if request.method == 'POST':
        # Process Audience scores (0-100 for each idea)
        for idea in Idea.query.all():
            score = request.form.get(f"score_{idea.id}")
            if score:
                #idea.score_audience = int(score)
                score = int(score)
                # Ensure score is within 0-50 and a multiple of 5
                if 0 <= score <= 50 and score % 5 == 0:
                    idea.score_audience = score
                else:
                    flash(f"Invalid score for Idea {idea.id}. Please enter a multiple of 5 between 0 and 50.", "danger")
                    return redirect(url_for('audience_dashboard'))  # Reload the page
        db.session.commit()  # Save changes to the database
        flash("Scores submitted successfully! Thank you for your participation.", "success")
        session.pop('user', None)  # Log out the user
        return redirect(url_for('thank_you'))  # Redirect to Thank You page
    return render_template('audience_dashboard.html', ideas=Idea.query.all())

# Route for Admin Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    calculate_total_scores() 
    winner = Idea.query.order_by(Idea.total_score.desc()).first() # Ensure total scores are calculated
    db.session.commit()
    return render_template('admin_dashboard.html', ideas=Idea.query.all(), winner=winner)

# Route for result page
@app.route('/result')
def result():
    calculate_total_scores()  # Update total scores for each idea
    return render_template('result.html', total_scores=Idea.query.all())

# Route for Thank You page
@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')

# **Add Users (Admin, Judge, Audience)**
@app.route('/add_users')
def add_users():
    users = [
        {"email": "vaishnai@amdocs.com", "role": "admin"},
        {"email": "ingawalevaishnavi8@gmail.com", "role": "judge"},
        {"email": "vaishnaviingawale1@gmail.com", "role": "audience"}
    ]
    for user in users:
        if not User.query.filter_by(email=user["email"]).first():
            new_user = User(email=user["email"], role=user["role"])
            db.session.add(new_user)
            send_mail(new_user.email, "Welcome!", f"Hello {new_user.role}, you have been added to the system.")
    db.session.commit()
    flash("✅ Users added!", "success")
    return redirect(url_for('home'))

if __name__ == '__main__':
    # Create tables before starting the app
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True)