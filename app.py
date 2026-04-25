from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import datetime
import json

app = Flask(__name__)
app.secret_key = 'krmangalam_premium_secret'

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT)')
    
    # Added is_available column to track stock
    conn.execute('CREATE TABLE IF NOT EXISTS menu (id INTEGER PRIMARY KEY, category TEXT, name TEXT, price REAL, description TEXT, emoji TEXT, is_available BOOLEAN DEFAULT 1)')
    conn.execute('CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, username TEXT, items TEXT, total REAL, status TEXT, timestamp TEXT)')
    
    # Safe update for existing local databases to add the new column
    try:
        conn.execute('ALTER TABLE menu ADD COLUMN is_available BOOLEAN DEFAULT 1')
    except sqlite3.OperationalError:
        pass # Column already exists
    
    if not conn.execute('SELECT * FROM users').fetchone():
        conn.execute("INSERT INTO users (username, password, role) VALUES ('student', 'pass', 'student')")
        conn.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin', 'admin')")
    
    if not conn.execute('SELECT * FROM menu').fetchone():
        menu_items = [
            ('Snacks', 'Crispy French Fries', 60, 'Salted potato fries served with ketchup', '🍟', 1),
            ('Snacks', 'Punjabi Samosa (2pcs)', 40, 'Hot samosas with mint and tamarind chutney', '🥟', 1),
            ('Fast Food', 'Margherita Pizza', 120, 'Classic cheese pizza with a thin crust', '🍕', 1),
            ('Fast Food', 'Aloo Tikki Burger', 70, 'Crispy patty with fresh veggies and mayo', '🍔', 1),
            ('Fast Food', 'White Sauce Pasta', 110, 'Creamy penne pasta with sweet corn and herbs', '🍝', 1),
            ('Meals', 'Rajma Chawal Bowl', 90, 'Authentic homestyle rajma with basmati rice', '🍛', 1),
            ('Meals', 'Chole Bhature (2pcs)', 100, 'Spicy punjabi chole with fluffy bhature', '🍲', 1),
            ('Beverages', 'Cold Coffee', 80, 'Thick blended coffee with chocolate syrup', '🧋', 1),
            ('Beverages', 'Fresh Lime Soda', 50, 'Refreshing sweet and salted lime drink', '🍹', 1)
        ]
        conn.executemany("INSERT INTO menu (category, name, price, description, emoji, is_available) VALUES (?, ?, ?, ?, ?, ?)", menu_items)
    
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            session['cart'] = []
            
            if user['role'] == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('menu'))
        else:
            flash('Invalid credentials. Try student/pass or admin/admin')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/menu', methods=['GET', 'POST'])
def menu():
    if 'username' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM menu ORDER BY category').fetchall()
    conn.close()
    
    if request.method == 'POST':
        item_id = int(request.form['item_id'])
        item_name = request.form['item_name']
        item_price = float(request.form['item_price'])
        
        cart = session.get('cart', [])
        cart.append({'id': item_id, 'name': item_name, 'price': item_price})
        session['cart'] = cart
        flash(f'🛒 {item_name} added to cart!')
        
    return render_template('menu.html', items=items, cart_count=len(session.get('cart', [])))

@app.route('/cart')
def cart():
    if 'username' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    cart_items = session.get('cart', [])
    total = sum(item['price'] for item in cart_items)
    return render_template('cart.html', cart=cart_items, total=total)

# --- NEW: PAYMENT ROUTES ---
@app.route('/payment', methods=['POST'])
def payment():
    if 'username' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    cart_items = session.get('cart', [])
    if not cart_items:
        return redirect(url_for('menu'))
        
    total = sum(item['price'] for item in cart_items)
    return render_template('payment.html', total=total)

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'username' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    cart_items = session.get('cart', [])
    if not cart_items:
        return redirect(url_for('menu'))
        
    total = sum(item['price'] for item in cart_items)
    items_str = json.dumps([item['name'] for item in cart_items])
    timestamp = datetime.datetime.now().strftime("%I:%M %p | %d %b")
    
    conn = get_db_connection()
    conn.execute('INSERT INTO orders (username, items, total, status, timestamp) VALUES (?, ?, ?, ?, ?)',
                 (session['username'], items_str, total, 'Pending', timestamp))
    conn.commit()
    conn.close()
    
    session['cart'] = []
    flash('✅ Payment Successful! Your order has been sent to the canteen.')
    return redirect(url_for('orders'))

@app.route('/orders')
def orders():
    if 'username' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user_orders = conn.execute('SELECT * FROM orders WHERE username = ? ORDER BY id DESC', (session['username'],)).fetchall()
    conn.close()
    
    parsed_orders = []
    for order in user_orders:
        order_dict = dict(order)
        order_dict['items'] = json.loads(order_dict['items'])
        parsed_orders.append(order_dict)
        
    return render_template('orders.html', orders=parsed_orders)

@app.route('/admin')
def admin():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    all_orders = conn.execute('SELECT * FROM orders ORDER BY id DESC').fetchall()
    # Fetch menu items for stock management
    menu_items = conn.execute('SELECT * FROM menu ORDER BY category').fetchall()
    conn.close()
    
    parsed_orders = []
    for order in all_orders:
        order_dict = dict(order)
        order_dict['items'] = json.loads(order_dict['items'])
        parsed_orders.append(order_dict)
        
    return render_template('admin.html', orders=parsed_orders, menu_items=menu_items)

@app.route('/update_order/<int:order_id>/<status>')
def update_order(order_id, status):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    valid_statuses = ['Preparing', 'Ready', 'Completed']
    if status in valid_statuses:
        conn = get_db_connection()
        conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
        conn.commit()
        conn.close()
        
    return redirect(url_for('admin'))

# --- NEW: STOCK MANAGEMENT ROUTE ---
@app.route('/toggle_stock/<int:item_id>')
def toggle_stock(item_id):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    item = conn.execute('SELECT is_available FROM menu WHERE id = ?', (item_id,)).fetchone()
    
    if item:
        # Flip the status: if 1 make it 0, if 0 make it 1
        new_status = 0 if item['is_available'] else 1
        conn.execute('UPDATE menu SET is_available = ? WHERE id = ?', (new_status, item_id))
        conn.commit()
        
    conn.close()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)