import os
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import quote

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(32)

# Database configuration (Supports local SQLite or Render PostgreSQL)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif database_url and database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///sokotz.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Master Admin Credentials
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS")

# ----------------- MODELS -----------------
class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)  # WhatsApp phone number
    location = db.Column(db.String(100), nullable=False)
    pin = db.Column(db.String(10), nullable=False, default="1234")  # Merchant PIN
    products = db.relationship('Product', backref='store', lazy=True, cascade='all, delete-orphan')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    store = db.relationship('Store', backref='orders', lazy=True)

# ----------------- STYLES & UI COMPONENTS -----------------
COMMON_STYLE = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    body { background-color: #f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .navbar { background: linear-gradient(135deg, #198754, #146c43); }
    .card { border: none; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .btn-success { background-color: #198754; border: none; }
    .btn-success:hover { background-color: #146c43; }
    #ai-widget { position: fixed; bottom: 20px; right: 20px; z-index: 1000; }
    #ai-chat-box { display: none; width: 320px; background: white; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.2); overflow: hidden; margin-bottom: 10px; }
    #ai-messages { height: 250px; overflow-y: auto; padding: 12px; background: #f9f9f9; font-size: 14px; }
</style>
"""

AI_WIDGET_HTML = """
<div id="ai-widget">
    <div id="ai-chat-box">
        <div class="bg-success text-white p-2 d-flex justify-content-between align-items-center">
            <span><i class="fa-solid fa-robot"></i> SokoTz AI Assistant</span>
            <button class="btn btn-sm text-white p-0" onclick="toggleAIChat()"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <div id="ai-messages">
            <div class="mb-2 text-muted">Habari! I am your SokoTz assistant. Ask me how to buy, register a store, or use the platform!</div>
        </div>
        <div class="p-2 border-top d-flex">
            <input type="text" id="ai-input" class="form-control form-control-sm me-1" placeholder="Type a question...">
            <button class="btn btn-success btn-sm" onclick="sendAIMessage()">Send</button>
        </div>
    </div>
    <button class="btn btn-success rounded-circle shadow-lg p-3" onclick="toggleAIChat()" style="width: 55px; height: 55px;">
        <i class="fa-solid fa-comments fa-lg"></i>
    </button>
</div>
<script>
function toggleAIChat() {
    const box = document.getElementById('ai-chat-box');
    box.style.display = box.style.display === 'block' ? 'none' : 'block';
}
function sendAIMessage() {
    const input = document.getElementById('ai-input');
    const msg = input.value.trim();
    if(!msg) return;
    const chatMsgs = document.getElementById('ai-messages');
    chatMsgs.innerHTML += `<div class="mb-2 text-end"><strong>You:</strong> ${msg}</div>`;
    input.value = '';
    
    let reply = "Karibu SokoTz! You can browse products by category, add them to your cart, and click 'Place Order' to send your order directly via WhatsApp to the seller.";
    const lower = msg.toLowerCase();
    if(lower.includes('sell') || lower.includes('store') || lower.includes('register')) {
        reply = "To sell on SokoTz, click on 'Register Store' in the navigation bar to create your shop, or log in via 'Store Login' using your PIN.";
    } else if(lower.includes('admin')) {
        reply = "Admins can access the control panel via the 'Admin' link in the top menu using master credentials.";
    }
    
    setTimeout(() => {
        chatMsgs.innerHTML += `<div class="mb-2 text-start text-success"><strong>AI:</strong> ${reply}</div>`;
        chatMsgs.scrollTop = chatMsgs.scrollHeight;
    }, 500);
}
</script>
"""

# ----------------- ROUTES -----------------

@app.route('/')
def index():
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    
    products_query = Product.query
    if query:
        products_query = products_query.filter(Product.name.ilike(f"%{query}%") | Product.description.ilike(f"%{query}%"))
    if category:
        products_query = products_query.filter_by(category=category)
        
    products = products_query.all()
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    cart = session.get('cart', {'items': []})
    cart_count = sum(item['qty'] for item in cart.get('items', []))
    
    return render_template_string(INDEX_TEMPLATE, products=products, categories=categories, query=query, selected_cat=category, cart_count=cart_count)

@app.route('/store/register', methods=['GET', 'POST'])
def register_store():
    if request.method == 'POST':
        name = request.form.get('name')
        owner_name = request.form.get('owner_name')
        phone = request.form.get('phone')
        location = request.form.get('location')
        pin = request.form.get('pin', '1234')
        
        store = Store(name=name, owner_name=owner_name, phone=phone, location=location, pin=pin)
        db.session.add(store)
        db.session.commit()
        session['store_id'] = store.id
        flash('Store registered successfully! Welcome to your dashboard.', 'success')
        return redirect(url_for('store_dashboard', store_id=store.id))
    return render_template_string(REGISTER_STORE_TEMPLATE)

@app.route('/store/login', methods=['GET', 'POST'])
def store_login():
    if request.method == 'POST':
        store_id = request.form.get('store_id')
        pin = request.form.get('pin')
        store = Store.query.get(store_id)
        if store and store.pin == pin:
            session['store_id'] = store.id
            flash('Login successful!', 'success')
            return redirect(url_for('store_dashboard', store_id=store.id))
        flash('Invalid store selection or incorrect PIN!', 'danger')
    stores = Store.query.all()
    return render_template_string(STORE_LOGIN_TEMPLATE, stores=stores)

@app.route('/store/logout')
def store_logout():
    session.pop('store_id', None)
    flash('Logged out of store dashboard.', 'info')
    return redirect(url_for('index'))

@app.route('/store/<int:store_id>')
def store_dashboard(store_id):
    if session.get('store_id') != store_id and not session.get('is_admin'):
        flash('Please log in with your store PIN to access your dashboard.', 'warning')
        return redirect(url_for('store_login'))
    store = Store.query.get_or_404(store_id)
    orders = Order.query.filter_by(store_id=store.id).all()
    return render_template_string(STORE_DASHBOARD_TEMPLATE, store=store, orders=orders)

@app.route('/store/<int:store_id>/add_product', methods=['POST'])
def add_product(store_id):
    if session.get('store_id') != store_id and not session.get('is_admin'):
        return redirect(url_for('store_login'))
    store = Store.query.get_or_404(store_id)
    name = request.form.get('name')
    price = float(request.form.get('price'))
    description = request.form.get('description')
    category = request.form.get('category')
    
    product = Product(store_id=store.id, name=name, price=price, description=description, category=category)
    db.session.add(product)
    db.session.commit()
    flash('Product added successfully!', 'success')
    return redirect(url_for('store_dashboard', store_id=store.id))

@app.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    store = product.store
    
    cart = session.get('cart')
    if not cart or cart.get('store_id') != store.id:
        cart = {'store_id': store.id, 'store_name': store.name, 'store_phone': store.phone, 'items': []}
        
    qty = int(request.form.get('qty', 1))
    existing_item = next((item for item in cart['items'] if item['id'] == product.id), None)
    if existing_item:
        existing_item['qty'] += qty
    else:
        cart['items'].append({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'qty': qty
        })
        
    session['cart'] = cart
    flash(f'Added {product.name} to cart!', 'success')
    return redirect(url_for('index'))

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    items = cart.get('items', [])
    total = sum(item['price'] * item['qty'] for item in items)
    return render_template_string(CART_TEMPLATE, cart=cart, total=total)

@app.route('/cart/remove/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart')
    if cart and 'items' in cart:
        cart['items'] = [item for item in cart['items'] if item['id'] != product_id]
        if not cart['items']:
            session.pop('cart', None)
        else:
            session['cart'] = cart
    return redirect(url_for('view_cart'))

@app.route('/place_order', methods=['POST'])
def place_order():
    cart = session.get('cart')
    if not cart or not cart.get('items'):
        flash('Your cart is empty!', 'danger')
        return redirect(url_for('index'))
        
    customer_name = request.form.get('customer_name')
    customer_phone = request.form.get('customer_phone')
    store_id = cart.get('store_id')
    store_phone = cart.get('store_phone')
    
    total = sum(item['price'] * item['qty'] for item in cart['items'])
    
    order = Order(store_id=store_id, customer_name=customer_name, customer_phone=customer_phone, total_amount=total)
    db.session.add(order)
    db.session.commit()
    
    msg = f"Habari! New Order from SokoTz:\n\nCustomer: {customer_name}\nPhone: {customer_phone}\n\nItems:\n"
    for item in cart['items']:
        msg += f"- {item['name']} x {item['qty']} (TZS {item['price'] * item['qty']:,.0f})\n"
    msg += f"\nTotal: TZS {total:,.0f}"
    
    whatsapp_url = f"https://wa.me/{store_phone}?text={quote(msg)}"
    session.pop('cart', None)
    
    return redirect(whatsapp_url)


# ----------------- ADMIN ROUTES -----------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['is_admin'] = True
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials!', 'danger')
    return render_template_string(ADMIN_LOGIN_TEMPLATE)

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    stores = Store.query.all()
    orders = Order.query.all()
    return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stores=stores, orders=orders)

@app.route('/admin/store/<int:store_id>/reset_pin', methods=['POST'])
def admin_reset_pin(store_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    store = Store.query.get_or_404(store_id)
    new_pin = request.form.get('new_pin', '1234')
    store.pin = new_pin
    db.session.commit()
    flash(f"PIN for {store.name} successfully reset to '{new_pin}'!", 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/store/<int:store_id>/delete', methods=['POST'])
def admin_delete_store(store_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    store = Store.query.get_or_404(store_id)
    db.session.delete(store)
    db.session.commit()
    flash('Store and its products deleted successfully.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    flash('Logged out of admin panel.', 'info')
    return redirect(url_for('index'))


# ----------------- TEMPLATES -----------------

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>SokoTz - Tanzania Local Marketplace</title>""" + COMMON_STYLE + """</head>
<body>
<nav class="navbar navbar-dark px-4 py-3 d-flex justify-content-between">
    <a class="navbar-brand fw-bold fs-4" href="/"><i class="fa-solid fa-store text-warning"></i> SokoTz Marketplace</a>
    <div>
        <a href="/cart" class="btn btn-outline-light me-2 position-relative"><i class="fa-solid fa-cart-shopping"></i> Cart {% if cart_count > 0 %}<span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger">{{cart_count}}</span>{% endif %}</a>
        <a href="/store/login" class="btn btn-outline-warning me-2"><i class="fa-solid fa-right-to-bracket"></i> Store Login</a>
        <a href="/store/register" class="btn btn-warning fw-semibold me-2"><i class="fa-solid fa-plus-circle"></i> Register Store</a>
        <a href="/admin/login" class="btn btn-dark btn-sm"><i class="fa-solid fa-lock"></i> Admin</a>
    </div>
</nav>
<div class="container my-4">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}{% for cat, msg in messages %}
        <div class="alert alert-{{cat}} alert-dismissible fade show" role="alert">{{msg}}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
      {% endfor %}{% endif %}
    {% endwith %}
    
    <div class="row mb-4">
        <div class="col-md-8 mx-auto text-center">
            <h1 class="fw-bold text-success">Discover Products Across Tanzania</h1>
            <p class="text-muted">Buy directly from local vendors in Dar es Salaam, Arusha, Mwanza and beyond via WhatsApp.</p>
            <form action="/" method="GET" class="input-group shadow-sm">
                <input type="text" name="q" class="form-control form-control-lg" placeholder="Search products (e.g. kitenge, viatu, simu)..." value="{{query}}">
                <button type="submit" class="btn btn-success px-4"><i class="fa-solid fa-search"></i> Search</button>
            </form>
        </div>
    </div>
    
    <div class="row">
        <div class="col-md-3 mb-4">
            <div class="card p-3">
                <h5 class="fw-bold mb-3"><i class="fa-solid fa-filter"></i> Categories</h5>
                <div class="list-group list-group-flush">
                    <a href="/" class="list-group-item list-group-item-action {% if not selected_cat %}active{% endif %}">All Categories</a>
                    {% for cat in categories %}
                    <a href="/?category={{cat}}" class="list-group-item list-group-item-action {% if selected_cat == cat %}active{% endif %}">{{cat}}</a>
                    {% endfor %}
                </div>
            </div>
        </div>
        <div class="col-md-9">
            <div class="row">
                {% if products %}
                    {% for p in products %}
                    <div class="col-md-4 mb-4">
                        <div class="card h-100 p-3 d-flex flex-column">
                            <span class="badge bg-secondary align-self-start mb-2">{{p.category}}</span>
                            <h5 class="fw-bold">{{p.name}}</h5>
                            <p class="text-muted small flex-grow-1">{{p.description}}</p>
                            <h6 class="text-success fw-bold mb-2">TZS {{ "{:,.0f}".format(p.price) }}</h6>
                            <p class="text-secondary small mb-3"><i class="fa-solid fa-shop"></i> Store: <strong>{{p.store.name}}</strong> (<i class="fa-solid fa-location-dot text-danger"></i> {{p.store.location}})</p>
                            <form action="/cart/add/{{p.id}}" method="POST" class="d-flex align-items-center">
                                <input type="number" name="qty" value="1" min="1" class="form-control form-control-sm me-2" style="width: 70px;">
                                <button type="submit" class="btn btn-success btn-sm w-100"><i class="fa-solid fa-cart-plus"></i> Add to Cart</button>
                            </form>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="col-12 text-center py-5"><h5 class="text-muted">No products found. Try a different search or register a store to add items!</h5></div>
                {% endif %}
            </div>
        </div>
    </div>
</div>
""" + AI_WIDGET_HTML + """
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

STORE_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Store Login - SokoTz</title>""" + COMMON_STYLE + """</head>
<body>
<nav class="navbar navbar-dark px-4"><a class="navbar-brand fw-bold" href="/"><i class="fa-solid fa-arrow-left"></i> Back to Marketplace</a></nav>
<div class="container my-5" style="max-width: 450px;">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}{% for cat, msg in messages %}
        <div class="alert alert-{{cat}} alert-dismissible fade show" role="alert">{{msg}}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
      {% endfor %}{% endif %}
    {% endwith %}
    <div class="card p-4">
        <h3 class="fw-bold mb-3 text-success"><i class="fa-solid fa-right-to-bracket"></i> Store Owner Login</h3>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label">Select Your Shop</label>
                <select name="store_id" class="form-select" required>
                    <option value="" disabled selected>Choose your store...</option>
                    {% for store in stores %}
                    <option value="{{store.id}}">{{store.name}} ({{store.location}})</option>
                    {% endfor %}
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label">Merchant PIN</label>
                <input type="password" name="pin" class="form-control" placeholder="Enter your 4-digit PIN" required>
            </div>
            <button type="submit" class="btn btn-success w-100 py-2"><i class="fa-solid fa-sign-in-alt"></i> Login to Dashboard</button>
        </form>
        <div class="text-center mt-3 small">
            Don't have a store yet? <a href="/store/register" class="text-success fw-bold">Register here</a>
        </div>
    </div>
</div>
""" + AI_WIDGET_HTML + """
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

REGISTER_STORE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Register Store - SokoTz</title>""" + COMMON_STYLE + """</head>
<body>
<nav class="navbar navbar-dark px-4"><a class="navbar-brand fw-bold" href="/"><i class="fa-solid fa-arrow-left"></i> Back to Marketplace</a></nav>
<div class="container my-5" style="max-width: 500px;">
    <div class="card p-4">
        <h3 class="fw-bold mb-3 text-success"><i class="fa-solid fa-store"></i> Register Your Shop</h3>
        <form method="POST">
            <div class="mb-3"><label class="form-label">Store Name</label><input type="text" name="name" class="form-control" placeholder="e.g. Kariakoo Fashion Hub" required></div>
            <div class="mb-3"><label class="form-label">Your Name (Owner)</label><input type="text" name="owner_name" class="form-control" placeholder="e.g. Juma Ally" required></div>
            <div class="mb-3"><label class="form-label">WhatsApp Phone Number</label><input type="text" name="phone" class="form-control" placeholder="e.g. 255712345678 (include country code)" required></div>
            <div class="mb-3"><label class="form-label">Location / City</label><input type="text" name="location" class="form-control" placeholder="e.g. Kariakoo, Dar es Salaam" required></div>
            <div class="mb-3"><label class="form-label">Merchant PIN (for security)</label><input type="password" name="pin" class="form-control" placeholder="4-digit PIN" required></div>
            <button type="submit" class="btn btn-success w-100 py-2"><i class="fa-solid fa-check-circle"></i> Create Store Dashboard</button>
        </form>
    </div>
</div>
""" + AI_WIDGET_HTML + """
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

STORE_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>{{store.name}} - Dashboard</title>""" + COMMON_STYLE + """</head>
<body>
<nav class="navbar navbar-dark px-4 d-flex justify-content-between">
    <a class="navbar-brand fw-bold" href="/"><i class="fa-solid fa-arrow-left"></i> Marketplace</a>
    <div>
        <span class="text-white me-3">Owner: <strong>{{store.owner_name}}</strong></span>
        <a href="/store/logout" class="btn btn-outline-light btn-sm">Logout</a>
    </div>
</nav>
<div class="container my-4">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}{% for cat, msg in messages %}
        <div class="alert alert-{{cat}} alert-dismissible fade show" role="alert">{{msg}}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
      {% endfor %}{% endif %}
    {% endwith %}

    <div class="card p-4 mb-4 bg-success text-white">
        <h2>{{store.name}}</h2>
        <p class="mb-1"><i class="fa-solid fa-location-dot"></i> Location: {{store.location}}</p>
        <p class="mb-0"><i class="fa-brands fa-whatsapp"></i> WhatsApp: {{store.phone}}</p>
    </div>
    
    <!-- Orders Received Section -->
    <div class="card p-4 mb-4">
        <h4 class="fw-bold mb-3 text-success"><i class="fa-solid fa-receipt"></i> Customer Orders for Your Shop</h4>
        <div class="table-responsive">
            <table class="table align-middle">
                <thead><tr><th>Order ID</th><th>Customer Name</th><th>Customer Phone</th><th>Total Amount</th></tr></thead>
                <tbody>
                    {% for order in orders %}
                    <tr>
                        <td>#{{order.id}}</td>
                        <td class="fw-bold">{{order.customer_name}}</td>
                        <td><a href="https://wa.me/{{order.customer_phone}}" target="_blank" class="text-dark"><i class="fa-brands fa-whatsapp text-success"></i> {{order.customer_phone}}</a></td>
                        <td class="text-success fw-bold">TZS {{ "{:,.0f}".format(order.total_amount) }}</td>
                    </tr>
                    {% else %}
                    <tr><td colspan="4" class="text-center text-muted">No orders received yet.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="row">
        <div class="col-md-4 mb-4">
            <div class="card p-3">
                <h4 class="fw-bold mb-3 text-success">Add New Product</h4>
                <form action="/store/{{store.id}}/add_product" method="POST">
                    <div class="mb-2"><label class="form-label">Product Name</label><input type="text" name="name" class="form-control" required></div>
                    <div class="mb-2"><label class="form-label">Price (TZS)</label><input type="number" step="any" name="price" class="form-control" required></div>
                    <div class="mb-2"><label class="form-label">Category</label><input type="text" name="category" class="form-control" placeholder="e.g. Clothing, Electronics" required></div>
                    <div class="mb-3"><label class="form-label">Description</label><textarea name="description" class="form-control" rows="3"></textarea></div>
                    <button type="submit" class="btn btn-success w-100">Add Product</button>
                </form>
            </div>
        </div>
        <div class="col-md-8">
            <div class="card p-3">
                <h4 class="fw-bold mb-3 text-success">Your Listed Products</h4>
                <div class="table-responsive">
                    <table class="table align-middle">
                        <thead><tr><th>Name</th><th>Category</th><th>Price</th><th>Description</th></tr></thead>
                        <tbody>
                            {% for p in store.products %}
                            <tr>
                                <td>{{p.name}}</td>
                                <td><span class="badge bg-secondary">{{p.category}}</span></td>
                                <td>TZS {{ "{:,.0f}".format(p.price) }}</td>
                                <td class="text-muted small">{{p.description}}</td>
                            </tr>
                            {% else %}
                            <tr><td colspan="4" class="text-center text-muted">No products listed yet. Use the form to add some!</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>
""" + AI_WIDGET_HTML + """
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

CART_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Shopping Cart - SokoTz</title>""" + COMMON_STYLE + """</head>
<body>
<nav class="navbar navbar-dark px-4"><a class="navbar-brand fw-bold" href="/"><i class="fa-solid fa-arrow-left"></i> Back to Marketplace</a></nav>
<div class="container my-4" style="max-width: 700px;">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}{% for cat, msg in messages %}
        <div class="alert alert-{{cat}} alert-dismissible fade show" role="alert">{{msg}}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
      {% endfor %}{% endif %}
    {% endwith %}
    <div class="card p-4">
        <h3 class="fw-bold mb-3 text-success"><i class="fa-solid fa-cart-shopping"></i> Your Shopping Cart</h3>
        {% if cart and cart.get('items') %}
        <h5 class="text-secondary mb-3">Store: <strong>{{cart.store_name}}</strong> (<i class="fa-brands fa-whatsapp text-success"></i> WhatsApp: {{cart.store_phone}})</h5>
        <div class="table-responsive">
            <table class="table align-middle">
                <thead><tr><th>Item</th><th>Price</th><th>Qty</th><th>Subtotal</th><th>Action</th></tr></thead>
                <tbody>
                    {% for item in cart.get('items') %}
                    <tr>
                        <td>{{item.name}}</td>
                        <td>TZS {{ "{:,.0f}".format(item.price) }}</td>
                        <td>{{item.qty}}</td>
                        <td>TZS {{ "{:,.0f}".format(item.price * item.qty) }}</td>
                        <td><a href="/cart/remove/{{item.id}}" class="btn btn-danger btn-sm py-0">Remove</a></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <h4 class="text-end fw-bold text-success mb-4">Total: TZS {{ "{:,.0f}".format(total) }}</h4>
        <form action="/place_order" method="POST" class="bg-light p-3 rounded">
            <h5 class="fw-bold mb-3"><i class="fa-brands fa-whatsapp text-success"></i> Complete & Send via WhatsApp</h5>
            <div class="mb-2"><input type="text" name="customer_name" class="form-control" placeholder="Your Name" required></div>
            <div class="mb-3"><input type="text" name="customer_phone" class="form-control" placeholder="Your Phone Number (e.g. 0712345678)" required></div>
            <button type="submit" class="btn btn-success w-100 py-2"><i class="fa-solid fa-paper-plane"></i> Place Order & Proceed to WhatsApp</button>
        </form>
        {% else %}
        <div class="text-center py-5"><p class="text-muted">Your cart is empty.</p><a href="/" class="btn btn-success btn-sm">Browse Marketplace</a></div>
        {% endif %}
    </div>
</div>
""" + AI_WIDGET_HTML + """
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

ADMIN_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Admin Login - SokoTz</title>""" + COMMON_STYLE + """</head>
<body>
<nav class="navbar navbar-dark px-4"><a class="navbar-brand fw-bold" href="/"><i class="fa-solid fa-arrow-left"></i> Back to Marketplace</a></nav>
<div class="container my-5" style="max-width: 400px;">
    <div class="card p-4">
        <h3 class="fw-bold mb-3 text-success text-center"><i class="fa-solid fa-lock"></i> Master Admin</h3>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}{% for cat, msg in messages %}
            <div class="alert alert-{{cat}} alert-dismissible fade show" role="alert">{{msg}}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
          {% endfor %}{% endif %}
        {% endwith %}
        <form method="POST">
            <div class="mb-3"><label class="form-label">Username</label><input type="text" name="username" class="form-control" autocomplete="off" required></div>
            <div class="mb-3"><label class="form-label">Password</label><input type="password" name="password" class="form-control" autocomplete="current-password" required></div>
            <button type="submit" class="btn btn-success w-100">Login to Control Panel</button>
        </form>
    </div>
</div>
""" + AI_WIDGET_HTML + """
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

ADMIN_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Admin Control Panel - SokoTz</title>""" + COMMON_STYLE + """</head>
<body>
<nav class="navbar navbar-dark px-4 d-flex justify-content-between">
    <a class="navbar-brand fw-bold" href="/"><i class="fa-solid fa-store"></i> SokoTz Admin Panel</a>
    <a href="/admin/logout" class="btn btn-outline-light btn-sm">Logout</a>
</nav>
<div class="container my-4">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}{% for cat, msg in messages %}
        <div class="alert alert-{{cat}} alert-dismissible fade show" role="alert">{{msg}}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
      {% endfor %}{% endif %}
    {% endwith %}

    <div class="row mb-4">
        <div class="col-md-6">
            <div class="card p-3 bg-success text-white">
                <h5>Total Registered Stores</h5>
                <h3 class="fw-bold">{{ stores | length }}</h3>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card p-3 bg-dark text-white">
                <h5>Total Platform Orders</h5>
                <h3 class="fw-bold">{{ orders | length }}</h3>
            </div>
        </div>
    </div>

    <!-- Stores & PIN Management / Review -->
    <div class="card p-4 mb-4">
        <h4 class="fw-bold mb-3 text-success"><i class="fa-solid fa-store"></i> Review Shops & Manage PINs</h4>
        <div class="table-responsive">
            <table class="table align-middle">
                <thead><tr><th>Store Name</th><th>Owner</th><th>Phone (WhatsApp)</th><th>Location</th><th>Current PIN</th><th>Actions</th></tr></thead>
                <tbody>
                    {% for store in stores %}
                    <tr>
                        <td class="fw-bold"><a href="/store/{{store.id}}" target="_blank" class="text-success text-decoration-none">{{store.name}} <i class="fa-solid fa-external-link-alt small"></i></a></td>
                        <td>{{store.owner_name}}</td>
                        <td><a href="https://wa.me/{{store.phone}}" target="_blank" class="text-dark"><i class="fa-brands fa-whatsapp text-success"></i> {{store.phone}}</a></td>
                        <td><i class="fa-solid fa-location-dot text-danger"></i> {{store.location}}</td>
                        <td><code>{{store.pin}}</code></td>
                        <td>
                            <form action="/admin/store/{{store.id}}/reset_pin" method="POST" class="d-inline-flex align-items-center me-2">
                                <input type="text" name="new_pin" placeholder="New PIN" class="form-control form-control-sm me-1" style="width: 90px;" required>
                                <button type="submit" class="btn btn-outline-warning btn-sm">Reset PIN</button>
                            </form>
                            <form action="/admin/store/{{store.id}}/delete" method="POST" class="d-inline" onsubmit="return confirm('Are you sure you want to delete this store and its products?');">
                                <button type="submit" class="btn btn-danger btn-sm">Delete</button>
                            </form>
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="6" class="text-center text-muted">No stores registered yet.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Platform Orders Monitoring -->
    <div class="card p-4">
        <h4 class="fw-bold mb-3 text-success"><i class="fa-solid fa-receipt"></i> Monitor All Platform Orders</h4>
        <div class="table-responsive">
            <table class="table align-middle">
                <thead><tr><th>Order ID</th><th>Store Name</th><th>Customer Name</th><th>Customer Phone</th><th>Total Amount</th></tr></thead>
                <tbody>
                    {% for order in orders %}
                    <tr>
                        <td>#{{order.id}}</td>
                        <td class="fw-bold">{{order.store.name}}</td>
                        <td>{{order.customer_name}}</td>
                        <td><a href="https://wa.me/{{order.customer_phone}}" target="_blank" class="text-dark"><i class="fa-brands fa-whatsapp text-success"></i> {{order.customer_phone}}</a></td>
                        <td class="text-success fw-bold">TZS {{ "{:,.0f}".format(order.total_amount) }}</td>
                    </tr>
                    {% else %}
                    <tr><td colspan="5" class="text-center text-muted">No orders placed yet.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
""" + AI_WIDGET_HTML + """
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# ----------------- INITIALIZATION -----------------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False)