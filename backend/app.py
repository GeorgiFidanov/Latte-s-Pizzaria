from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from bson import ObjectId


load_dotenv()
mongoDB_connection = os.getenv("mongoDB_connection")


app = Flask(__name__)
app.secret_key = os.getenv("secret_key")


# MongoDB setup
client = MongoClient(mongoDB_connection)
db = client['Latte\'s_Pizzeria']
users_collection = db['Users']
orders_collection = db['Orders']


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


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        address = request.form['address']
        gender = request.form['gender']
        terms = request.form.get('terms')  # This will be 'on' if checked, otherwise None
        ads = request.form.get('ads')  # Same as previous

        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
            return render_template('register.html')

        # Check if the username already exists
        if users_collection.find_one({'username': username}):
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html')

        # Check if email already exists
        if users_collection.find_one({'email': email}):
            flash('Email already registered. Please use a different one.', 'danger')
            return render_template('register.html')

        if terms is None:
            flash('You must agree to the terms and conditions.', 'danger')
            return render_template('register.html')


        # Hash the password for security
        hashed_password = generate_password_hash(password)

        # Save user data to the database
        users_collection.insert_one({
            'username': username,
            'email': email,
            'password': hashed_password,
            'address': address,
            'gender': gender,
            'ad_preferences': bool(ads),
            'agreed_to_terms': bool(terms)
        })

        # Log in the user automatically and redirect to the menu page
        session['username'] = username
        flash('Registration successful! Welcome to the pizzeria.', 'success')
        return redirect(url_for('menu'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({'username': username})

        if username in login_attempts and login_attempts[username] >= 3:
            flash('Too many login attempts. Please try again later.', 'danger')
            return redirect(url_for('login'))

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            login_attempts[username] = 0  # Reset attempts on successful login

            if username == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('menu'))
        
        else:
            login_attempts[username] = login_attempts.get(username, 0) + 1
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("You have been logged out.", 'info')
    return redirect(url_for('login'))


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = users_collection.find_one({'email': email})

        if user:
            token = os.urandom(24).hex()  # Generating a simple reset token
            users_collection.update_one({'_id': user['_id']}, {'$set': {'reset_token': token}})
            reset_url = url_for('reset_password', token=token, _external=True)

            msg = Message('Password Reset Request', sender=os.getenv('EMAIL_USER'), recipients=[email])
            msg.body = f'To reset your password, click the following link: {reset_url}'
            mail.send(msg)

            flash('An email has been sent with instructions to reset your password.', 'info')

        else:
            flash('Email address not found.', 'danger')

    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = users_collection.find_one({'reset_token': token})

    if not user:
        flash('Invalid or expired reset token.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password == confirm_password:
            hashed_password = generate_password_hash(new_password)
            users_collection.update_one(
                {'_id': user['_id']},
                {'$set': {'password': hashed_password, 'reset_token': None}}
            )

            flash('Your password has been updated successfully.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Passwords do not match. Please try again.', 'danger')

    return render_template('reset_password.html')


@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    if 'username' in session:
        users_collection.delete_one({'username': session['username']})
        session.pop('username', None)
        flash("Your profile has been deleted.", 'info')
    return redirect(url_for('register'))


@app.route('/menu', methods=['GET', 'POST'])
def menu():
    pizzas = [  # Menu items
        {'name': 'Margherita', 'price': 8},
        {'name': 'Pepperoni', 'price': 10},
    ]
    if request.method == 'POST':
        order_item = {pizza['name']: int(request.form.get(pizza['name'], 0)) for pizza in pizzas}
        session['order'] = order_item
        return redirect(url_for('order'))

    return render_template('menu.html', pizzas=pizzas)


current_id = 0
reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
def get_id():
    global current_id, reset_time
    now = datetime.now()

    if now >= reset_time:
        current_id = 0
        reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    current_id += 1
    return current_id


@app.route('/order', methods=['GET', 'POST'])
def order():
    order = session.get('order', {})
    if request.method == 'POST':
        payment_method = request.form['payment_method']
        order_id = get_id()
        order_time = datetime.now()
        estimated_time = order_time + timedelta(minutes=20)

        # Save the order
        order_details = {'username': session.get('username', 'guest'), 'order_id': order_id, 
                         'order_time': order_time, 'order_details': order, 
                         'status': 'Unpaid', 'estimated_time': estimated_time,
                         'payment_method': payment_method}
        
        orders_collection.insert_one(order_details)
        
        if payment_method == 'card':

            flash('Processing card payment...', 'info')
            return redirect(url_for('simulate_card_payment', order_id=order_id))
        
        elif payment_method == 'cash':

            return redirect(url_for('cash_payment_loading', order_id=order_id))

    return render_template('order.html', order=order)


@app.route('/simulate_card_payment/<order_id>')
def simulate_card_payment(order_id):
    # Simulate successful card payment
    order = orders_collection.find_one({'order_id': int(order_id)})  # Find the specific order
    
    if order:
        orders_collection.update_one(
            {'order_id': int(order_id)}, 
            {'$set': {'status': 'Paid'}}
        )
        flash('Payment successful! Thank you for your order.', 'success')
    else:
        flash('Order not found.', 'danger')
    
    return redirect(url_for('thank_you'))


@app.route('/cash_payment_loading/<order_id>')
def cash_payment_loading(order_id):
    return render_template('cash_payment_loading.html', order_id=order_id)


@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')


@app.route('/about')
def about():
    return render_template('about_us.html')


@app.route('/terms_and_conditions')
def terms_and_conditions():
    return render_template('terms_and_conditions.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'username' not in session or session['username'] != 'admin':
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        order_id = request.form.get('order_id')
        new_status = request.form.get('status')
        # Update the status of the specified order in MongoDB
        orders_collection.update_one({'_id': ObjectId(order_id)}, {'$set': {'status': new_status}})

    # Retrieve orders created within the last hour
    one_hour_ago = datetime.now() - timedelta(hours=1)
    recent_orders = list(orders_collection.find({'order_time': {'$gte': one_hour_ago}}))

    return render_template('admin.html', orders=recent_orders)


if __name__ == '__main__':
    app.run(debug=True)
