import pymysql
pymysql.install_as_MySQLdb()

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy

import random
import string
import win32com.client
import time
import pythoncom
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'hello123'  # Use a strong secret key in production

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

# Function to send OTP email using Outlook
def send_mail(email, subject, message):
    try:
        # Initialize COM before creating an Outlook application instance
        pythoncom.CoInitialize()
        
        # Create an instance of Outlook
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail_item = outlook.CreateItem(0)  # 0: MailItem

        # Set the properties of the email
        mail_item.Subject = subject
        mail_item.Body = message
        mail_item.To = email

        # Save the message to Sent Items (debugging step)
        mail_item.Save()

        # Force sending the email
        mail_item.Send()

        print("Email sent successfully")

    except Exception as e:
        print(f"Error sending email: {e}")

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
            subject = "Your OTP Code"
            message = f"Your OTP code is: {otp}"
            send_mail(email, subject, message)

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
                idea.score_judge = int(score)
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
                idea.score_audience = int(score)
        db.session.commit()  # Save changes to the database
        flash("Scores submitted successfully! Thank you for your participation.", "success")
        session.pop('user', None)  # Log out the user
        return redirect(url_for('thank_you'))  # Redirect to Thank You page
    return render_template('audience_dashboard.html', ideas=Idea.query.all())

# Route for Admin Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    calculate_total_scores() 
    ideas = Idea.query.all()
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

# Route to add users to the database (admin, judge, and audience)
@app.route('/add_users')
def add_users():
    # Add admin user
    admin_user = User.query.filter_by(email="vaishnaviingawale1@gmail.com").first()
    if not admin_user:
        admin_user = User(email="vaishnaviingawale1@gmail.com", role="admin")
        db.session.add(admin_user)

    # Add judge user
    judge_user = User.query.filter_by(email="vingawale05@gmail.com").first()
    if not judge_user:
        judge_user = User(email="vingawale05@gmail.com", role="judge")
        db.session.add(judge_user)

    # Add audience user
    audience_user = User.query.filter_by(email="vaishnai@amdocs.com").first()
    if not audience_user:
        audience_user = User(email="vaishnai@amdocs.com", role="audience")
        db.session.add(audience_user)

    db.session.commit()
    flash("Users added successfully!", "success")
    return redirect(url_for('home'))


if __name__ == '__main__':
    # Create tables before starting the app
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True)

