import pymysql
pymysql.install_as_MySQLdb()

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
from os import getenv

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hello123')  # Secure key

# Enable Flask-SocketIO with CORS to allow mobile access
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuring MySQL database
DATABASE_URL = getenv('DATABASE_URL', 'mysql+pymysql://root:11111@127.0.0.1:3306/voting_db')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
db = SQLAlchemy(app)
#db_url = os.environ.get('DATABASE_URL', 'mysql+pymysql://root:11111@localhost/voting_db')
#app.config['SQLALCHEMY_DATABASE_URI'] = db_url
#app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

login_manager = LoginManager(app)
login_manager.login_view = 'home'

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False)

# Idea Model
class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    score_judge = db.Column(db.Integer, default=0)
    score_audience = db.Column(db.Integer, default=0)
    total_score = db.Column(db.Integer, default=0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Home/Login Page
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        email = request.form['email']
        role = request.form['role']
        user = User.query.filter_by(email=email, role=role).first()
        if user:
            login_user(user)
            session.permanent = True  # Keep user logged in
            return redirect(url_for(f'{role}_dashboard'))
        flash("Invalid email or role.", "danger")
    return render_template('login.html')

# Login Route
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    role = request.form['role']

    # Check if the user already exists
    user = User.query.filter_by(email=email, role=role).first()

    # If role is "audience", auto-create the user if they don't exist
    if role == "audience" and not user:
        user = User(email=email, role=role)
        db.session.add(user)
        db.session.commit()

    if user:
        login_user(user)
        session.permanent = True  # Keep session active
        return redirect(url_for(f'{role}_dashboard'))  
    else:
        flash("Invalid email or role!", "danger")
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

# Thank You Page
@app.route('/thankyou')
def thankyou():
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




if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Running on 0.0.0.0 to allow access from mobile devices in the same network
    socketio.run(app, debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
