from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message


load_dotenv()
mongoDB_connection = os.getenv("mongoDB_connection")

app = Flask(__name__)
app.secret_key = os.getenv("secret_key")

# MongoDB setup
client = MongoClient(mongoDB_connection)
db = client['pizzeria_db']
users_collection = db['users']
orders_collection = db['orders']


app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
mail = Mail(app)

# Track login attempts
login_attempts = {}

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({'username': username})

        if username in login_attempts and login_attempts[username] >= 3:
            flash('Too many login attempts. Please try again later.', 'danger')
            return redirect(url_for('login'))

        if user and user['password'] == password:
            session['username'] = username
            login_attempts[username] = 0  # Reset attempts on successful login
            return redirect(url_for('menu'))
        else:
            login_attempts[username] = login_attempts.get(username, 0) + 1
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = users_collection.find_one({'email': email})

        if user:
            token = os.urandom(24).hex()  # Generating a simple reset token
            reset_url = url_for('reset_password', token=token, _external=True)

            msg = Message('Password Reset Request',
                          sender='noreply@pizzeria.com',
                          recipients=[email])
            msg.body = f'To reset your password, click the following link: {reset_url}'
            mail.send(msg)

            flash('An email has been sent with instructions to reset your password.', 'info')
        else:
            flash('Email address not found.', 'danger')

    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password == confirm_password:
            # Logic to update the user's password in the database
            flash('Your password has been updated.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Passwords do not match.', 'danger')

    return render_template('reset_password.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if users_collection.find_one({'username': username}):
            return 'Username already exists'
        hashed_password = generate_password_hash(password)
        users_collection.insert_one({'username': username, 'password': hashed_password})
        session['username'] = username
        return redirect(url_for('menu'))
    return render_template('register.html')


@app.route('/menu', methods=['GET', 'POST'])
def menu():
    pizzas = [
        {'name': 'Margherita', 'price': 8},
        {'name': 'Pepperoni', 'price': 10},
    ]
    if request.method == 'POST':
        order = {pizza['name']: int(request.form.get(pizza['name'], 0)) for pizza in pizzas}
        session['order'] = order
        return redirect(url_for('order'))

    return render_template('menu.html', pizzas=pizzas)



@app.route('/order', methods=['GET', 'POST'])
def order():
    if request.method == 'POST':
        order_details = request.form.getlist('pizzas')
        estimated_time = '20 minutes'  # Static estimated time for now
        orders_collection.insert_one({'username': session['username'], 'order_details': order_details, 'status': 'Pending'})
        return redirect(url_for('thank_you'))
    return render_template('order.html', orders=session.get('orders'), estimated_time='20 minutes')


@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')


@app.route('/about')
def about():
    return render_template('about_us.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
