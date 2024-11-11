import random
from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from bson import ObjectId
import stripe
from flask_apscheduler import APScheduler

load_dotenv()
mongoDB_connection = os.getenv("mongoDB_connection")
stripe.api_key = os.getenv("STRIPE_API_KEY")


app = Flask(__name__)
app.secret_key = os.getenv("secret_key")


# MongoDB setup
client = MongoClient(mongoDB_connection)
db = client['Latte\'s_Pizzeria']
users_collection = db['Users']
orders_collection = db['Orders']
coupons_collection = db['Coupons']


# app.config['MAIL_DEBUG'] = True
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
app.config['SERVER_NAME'] = 'localhost:5000'
app.config['PREFERRED_URL_SCHEME'] = 'http'

mail = Mail(app)
scheduler = APScheduler()

# Track login attempts
login_attempts = {}


@app.route('/')
def index():
    if 'username' not in session:
        session['username'] = 'Guest'
        session['guest'] = True

    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():

    if 'username' not in session:
        session['username'] = 'Guest'
        session['guest'] = True

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        address = request.form['address']
        gender = request.form['gender']
        terms = request.form.get('terms')  # This will be 'on' if checked, otherwise None
        ads = request.form.get('ads')  # Same as previous

        # Validate Username
        if len(username) < 3:
            flash('Username must be at least 3 characters long.', 'danger')
            return render_template('register.html')

        # Validate Email
        if '@' not in email or '.' not in email.split('@')[1]:
            flash('Please enter a valid email address.', 'danger')
            return render_template('register.html')

        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
            return render_template('register.html')

        # Check if the password is strong enough (at least 8 characters)
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('register.html')

        # Check if username already exists in the database
        if users_collection.find_one({'username': username}):
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html')

        # Check if email already exists in the database
        if users_collection.find_one({'email': email}):
            flash('Email already registered. Please use a different one.', 'danger')
            return render_template('register.html')

        # Validate that terms and conditions are checked
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
            'agreed_to_terms': True,
            'confirmed' : False
        })

        # Log in the user automatically and redirect to the menu page
        session['username'] = username
        session['guest'] = False
        flash('Registration successful! Welcome to the pizzeria.', 'success')

        user = users_collection.find_one({'username': username})
        token = os.urandom(24).hex()  # Generating a simple confirm token
        users_collection.update_one({'_id': user['_id']}, {'$set': {'confirm_token': token}})
        confirm_url = url_for('profile_confirmation', token=token, _external=True)

        msg = Message('Profile conformation', sender=os.getenv('EMAIL_USER'), recipients=[email])
        msg.body = f'To confirm your profile, click the following link: {confirm_url}'
        mail.send(msg)

        flash('An email has been sent with instructions to reset your password.', 'info')


        return redirect(url_for('menu'))

    return render_template('register.html')


@app.route('/profile_confirmation/<token>', methods=['GET', 'POST'])
def profile_confirmation(token):
    user = users_collection.find_one({'confirm_token': token})

    if not user:
        flash('Invalid or expired reset token.', 'danger')
        return redirect(url_for('register'))

    users_collection.update_one(
                {'_id': user['_id']},
                {'$set': {'confirmed': True, 'confirm_token': None}}
            )
    return redirect(url_for('index'))


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
            session['guest'] = False
            login_attempts[username] = 0  # Reset attempts on successful login

            if username == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('menu'))
        
        else:
            login_attempts[username] = login_attempts.get(username, 0) + 1
            flash('Invalid username or password.', 'danger')

    if 'username' not in session:
        session['username'] = 'Guest'
        session['guest'] = True

    return render_template('login.html')


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    # Assume user is logged in, fetch their data
    if 'username' not in session:
        session['username'] = 'Guest'
        session['guest'] = True

    user = users_collection.find_one({'username': session['username']})

    if user == "Guest" or user == "admin":
        flash('Please, log in to edit your profile.', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Get updated data from form fields
        updated_data = {
            'username': request.form['username'],
            'email': request.form['email'],
            'address': request.form['address'],
            'gender': request.form['gender'],
            'ad_preferences': bool(request.form.get('ads'))
        }

        # Update user information in the database
        users_collection.update_one({'username': session['username']}, {'$set': updated_data})
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('menu'))

    return render_template('edit_profile.html', user=user)


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("You have been logged out.", 'info')
    session['username'] = 'Guest'

    return redirect(url_for('login'))


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():

    if 'username' not in session:
        return redirect(url_for('login'))

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


menu_items = [  # Menu items
        {'name': 'Margherita', 'price': 8},
        {'name': 'Pepperoni', 'price': 10},
    ]


@app.route('/menu', methods=['GET', 'POST'])
def menu():

    global menu_items
    if 'username' not in session:
        session['username'] = 'Guest'
        session['guest'] = True
        
    if request.method == 'POST':
        order_item = {pizza['name']: int(request.form.get(pizza['name'], 0)) for pizza in menu_items}
        session['order'] = order_item
        return redirect(url_for('order'))

    # Pre-fill order quantities if editing
    if session['username'] != 'Guest':
        order_item = session.get('order', {})
        return render_template('menu.html', pizzas=menu_items, order_item=order_item)
    
    return render_template('menu.html', pizzas=menu_items, order_item={})


@app.route('/order', methods=['GET', 'POST'])
def order():

    if 'username' not in session:
        session['username'] = 'Guest'
        session['guest'] = True


    global menu_items
    client_order = session.get('order', {})

    if not any(client_order.values()):
        flash("Your order is empty. Please add items from the menu.", 'error')
        return redirect(url_for('menu'))
    
    estimated_time = datetime.now() + timedelta(minutes=20)
    
    # Prepare order summary
    order_summary = []
    total_amount = 0

    for name, quantity in client_order.items():
        quantity = int(quantity)
        if quantity > 0:
            price_per_item = next((item['price'] for item in menu_items if item['name'] == name), 0)
            total_price = price_per_item * quantity
            total_amount += total_price
            order_summary.append({
                'name': name,
                'quantity': quantity,
                'price_per_item': price_per_item,
                'total_price': total_price
            })

    # Check if promo code is applied
    promo_code = request.form.get('promo_code')
    discount = 0

    if promo_code:
        # Retrieve the coupon from the database
        coupon = coupons_collection.find_one({"code": promo_code})
        
        if coupon:
            # Check if the coupon has expired
            expiration_date = coupon['expires_at']   # Convert from milliseconds
            if expiration_date > datetime.now():
                # Apply the discount based on the coupon value
                if coupon['value'] == '10%':
                    discount = total_amount * 0.10  # Apply 10% discount
                    flash(f'Promo code applied! You get €{discount:.2f} off.', 'success')
            else:
                flash('This promo code has expired.', 'error')
        else:
            flash('Invalid promo code. Please try again.', 'error')

    # Apply discount to total amount
    total_amount -= discount

    if request.method == 'POST':

        if 'edit_order' in request.form:
            return redirect(url_for('menu'))
        
        elif 'delete_order' in request.form:
            session.pop('order', None)
            flash("Order deleted.", 'info')
            return redirect(url_for('menu'))

        else:
            payment_method = request.form.get('payment_method')
            order_id = random.randint(1000, 9999)

            order_details = {
                'username': session.get('username', 'Guest'),
                'order_id': order_id,
                'order_time': datetime.now(),
                'order_summary': order_summary,
                'total_amount': total_amount,
                'estimated_time': estimated_time,
                'status': 'Unpaid',
                'payment_method': payment_method
            }
            # Redirect based on payment method
            if payment_method == 'card':
                flash('Processing card payment...', 'info')
                orders_collection.insert_one(order_details)
                return redirect(url_for('simulate_card_payment', order_id=order_id))
            
            elif payment_method == 'cash':
                flash('You chose to pay with cash. Please pay at the counter upon pickup.', 'info')
                orders_collection.insert_one(order_details)
                return redirect(url_for('cash_payment', order_id=order_id))

    return render_template('order.html', order_summary=order_summary, total_amount=total_amount)


@app.route('/simulate_card_payment/<order_id>')
def simulate_card_payment(order_id):    
    card_order = orders_collection.find_one({'order_id': int(order_id)})

    if card_order:
        """
        # Use Stripe test card info for payment simulation
        payment_intent = stripe.PaymentIntent.create(
            amount=int(order['total_amount']), 
            currency="euro",
            payment_method_types=["card"]
        )
        """
        orders_collection.update_one({'order_id': int(order_id)}, {'$set': {'status': 'Paid'}})
        flash('Payment successful! Thank you for your order.', 'success')
        return redirect(url_for('thank_you', order_id=order_id))
    else:
        flash('Order not found.', 'danger')
        return redirect(url_for('order'))
            


@app.route('/cash_payment/<order_id>')
def cash_payment(order_id):

    cash_order = orders_collection.find_one({'order_id': int(order_id)})

    # Check if the order has been marked as 'Paid' by the admin
    if cash_order and cash_order['status'] == 'Paid':
        flash('Payment successful! Thank you for your order.', 'success')
        return redirect(url_for('thank_you', order_id=order_id))

    return render_template('cash_payment.html', order_id=order_id)


@app.route('/thank_you/<order_id>')
def thank_you(order_id):
    ready_order = orders_collection.find_one({'order_id': int(order_id)})
    estimated_time = ready_order['estimated_time']

    if ready_order['status'] == 'Ready':
        flash('Your order is ready to pick up!', 'info')

    if ready_order['status'] == 'Completed':
        flash('Order completed! Enjoy!', 'success')

    return render_template('thank_you.html', estimated_time=estimated_time, order_id=order_id)


@app.route('/about_us')
def about_us():
    if 'username' not in session:
        session['username'] = 'Guest'
        session['guest'] = True

    return render_template('about_us.html')


@app.route('/terms_and_conditions')
def terms_and_conditions():
    if 'username' not in session:
        session['username'] = 'Guest'
        session['guest'] = True

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



@app.route('/screen')
def screen():
    if 'username' not in session or session['username'] != 'admin':
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('login'))

    one_hour_ago = datetime.now() - timedelta(hours=1)
    ready_orders = list(orders_collection.find({
        'order_time': {'$gte': one_hour_ago},
        'status': 'Ready'
    }))
    return render_template('screen.html', orders=ready_orders)


def generate_and_send_coupons():

    with app.app_context():  # Ensure the app context is available
        # Get all subscribed users
        subscribed_users = users_collection.find({'ad_preferences': True})

        # Generate a unique coupon code
        coupon_code = f"{os.urandom(6).hex()}"

        # Add coupon code to database with expiration in 2 days
        coupon = {
            'code': coupon_code,
            'expires_at': datetime.now() + timedelta(days=2),
            'value': '10%'
        }
        coupons_collection.insert_one(coupon)

        # Send coupon email to each subscribed user
        for user in subscribed_users:
            email = user['email']
            user_id = user['_id']
            unsubscribe_url = url_for('unsubscribe', user_id=str(user_id), _external=True)
            username = user['username']

            gender = user['gender']
            if gender == 'Male':
                gender_term = ' Mr.'
            elif gender == 'Female':
                gender_term = ' Ms./Mrs.'
            else:
                gender_term = ''

            msg = Message(f'Dear,{gender_term} {username}, \nYour New Coupon Code!', sender=os.getenv('EMAIL_USER'), recipients=[email])
            msg.body = f"Your coupon code is {coupon_code}. It expires in 2 days.\n" \
                       f"If you want to unsubscribe from future coupons, click here: {unsubscribe_url}"
            mail.send(msg)


scheduler.add_job(id='send_coupons', func=generate_and_send_coupons, trigger='interval', days=2)
scheduler.start()


@app.route('/unsubscribe/<user_id>', methods=['GET', 'POST'])
def unsubscribe(user_id):
    users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'subscribed': False}})
    flash("You have successfully unsubscribed from receiving future coupon emails.", 'info')
    return redirect(url_for('index'))


@app.errorhandler(404)
def page_not_found(e):
    if 'username' not in session:
        session['username'] = 'Guest'
        session['guest'] = True
    return render_template('404.html', pages=e), 404


if __name__ == '__main__':
    app.run(debug=True)
    scheduler.init_app(app)
    scheduler.start()
