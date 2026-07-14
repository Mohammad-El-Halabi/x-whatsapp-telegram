import os
import sys
import logging
import uuid
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from src.config.settings import SECRET_KEY, DEBUG
from src.services.supabase_service import SupabaseService

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if getattr(sys, 'frozen', False):
    _src_dir = sys._MEIPASS

app = Flask(__name__,
            template_folder=os.path.join(_src_dir, 'templates'),
            static_folder=os.path.join(_src_dir, 'static'))
app.secret_key = SECRET_KEY
app.config['DEBUG'] = DEBUG

supabase = SupabaseService()


def is_admin():
    if 'user_id' not in session:
        return False
    user = supabase.get_user_by_id(session['user_id'])
    return user and user.role in ['superadmin', 'admin']


def is_superadmin():
    if 'user_id' not in session:
        return False
    user = supabase.get_user_by_id(session['user_id'])
    return user and user.role == 'superadmin'


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_admin():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def csrf_check(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "POST":
            token = request.form.get('csrf_token')
            if not token or token != session.get('csrf_token'):
                flash('Invalid form submission, please try again', 'error')
                return redirect(request.url)
        return f(*args, **kwargs)
    return decorated


@app.before_request
def log_requests():
    if request.path.startswith('/api/'):
        return
    logger.info(f"{request.method} {request.path}")


@app.context_processor
def inject_csrf():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return {'csrf_token': session['csrf_token']}


@app.route('/')
def index():
    if 'user_id' in session and is_admin():
        stats = supabase.get_dashboard_stats()
        return render_template('dashboard.html', stats=stats)
    return redirect(url_for('login'))


# ===================== ADMIN LOGIN =====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('login.html')
        auth_data = supabase.login_with_email(email, password)
        if auth_data:
            user = supabase.get_user_by_id(auth_data['id'])
            if user and user.role in ['superadmin', 'admin']:
                session['user_id'] = user.id
                session['user_role'] = user.role
                session['user_name'] = user.full_name
                logger.info(f"Admin {user.email} logged in")
                return redirect(url_for('index'))
            supabase.sign_out()
        flash('Invalid credentials or insufficient permissions', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    supabase.sign_out()
    session.clear()
    return redirect(url_for('login'))


# ===================== ADMIN USER MANAGEMENT =====================

@app.route('/users')
@admin_required
def users():
    users_list = supabase.get_all_users()
    offices = {o.id: o for o in supabase.get_all_offices()}
    if not is_superadmin():
        users_list = [u for u in users_list if u.role != 'superadmin']
    return render_template('users.html', users=users_list, offices=offices, is_superadmin=is_superadmin())


@app.route('/users/create', methods=['POST'])
@admin_required
@csrf_check
def create_user():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    full_name = request.form.get('full_name', '').strip()
    role = request.form.get('role', 'staff')
    office_id = request.form.get('office_id') or None
    if not email or not password or not full_name:
        flash('All fields are required', 'error')
        return redirect(url_for('users'))
    user = supabase.create_user_with_auth(email, password, full_name, role, office_id)
    if user:
        flash('User created successfully', 'success')
        logger.info(f"Created user {email}")
    else:
        flash('Failed to create user. The email may already be registered.', 'error')
    return redirect(url_for('users'))


@app.route('/users/<user_id>/edit', methods=['POST'])
@admin_required
@csrf_check
def edit_user(user_id):
    data = {
        'full_name': request.form.get('full_name', '').strip(),
        'role': request.form.get('role', 'staff'),
        'is_active': request.form.get('is_active') == 'on',
        'office_id': request.form.get('office_id') or None
    }
    password = request.form.get('password', '').strip()
    if password:
        if supabase.update_user_password(user_id, password):
            flash('Password updated', 'success')
        else:
            flash('Failed to update password', 'error')
    if supabase.update_user(user_id, data):
        flash('User updated', 'success')
    else:
        flash('Failed to update user', 'error')
    return redirect(url_for('users'))


@app.route('/users/<user_id>/delete', methods=['POST'])
@admin_required
@csrf_check
def delete_user(user_id):
    if supabase.delete_user(user_id):
        flash('User deleted', 'success')
    else:
        flash('Failed to delete user', 'error')
    return redirect(url_for('users'))


# ===================== ASSIGNMENTS =====================

@app.route('/assignments')
@admin_required
def assignments():
    assignments_list = supabase.get_all_assignments()
    users = {u.id: u for u in supabase.get_all_users()}
    return render_template('assignments.html', assignments=assignments_list, users=users)


@app.route('/assignments/create', methods=['POST'])
@admin_required
@csrf_check
def create_assignment():
    data = {
        'id': str(uuid.uuid4()),
        'user_id': request.form.get('user_id'),
        'platform': request.form.get('platform', '').strip().lower(),
        'phone_number': request.form.get('phone_number', '').strip(),
        'gateway_number': request.form.get('gateway_number', '').strip(),
        'display_name': request.form.get('display_name', '').strip(),
        'is_active': request.form.get('is_active') == 'on'
    }
    if data['platform'] not in ['telegram', 'whatsapp']:
        flash('Choose Telegram or WhatsApp', 'error')
        return redirect(url_for('assignments'))
    if not data['user_id'] or not data['phone_number'] or not data['gateway_number']:
        flash('Staff, platform, phone number, and gateway are required', 'error')
        return redirect(url_for('assignments'))
    result = supabase.create_assignment(data)
    if result:
        flash('Assignment created', 'success')
    else:
        flash('Failed to create assignment', 'error')
    return redirect(url_for('assignments'))


@app.route('/assignments/<assignment_id>/edit', methods=['POST'])
@admin_required
@csrf_check
def edit_assignment(assignment_id):
    data = {
        'platform': request.form.get('platform', '').strip().lower(),
        'phone_number': request.form.get('phone_number', '').strip(),
        'gateway_number': request.form.get('gateway_number', '').strip(),
        'display_name': request.form.get('display_name', '').strip(),
        'is_active': request.form.get('is_active') == 'on',
        'connection_status': request.form.get('connection_status')
    }
    if data['platform'] not in ['telegram', 'whatsapp'] or not data['phone_number'] or not data['gateway_number']:
        flash('Platform, account phone, and gateway are required', 'error')
        return redirect(url_for('assignments'))
    if supabase.update_assignment(assignment_id, data):
        flash('Assignment updated', 'success')
    else:
        flash('Failed to update assignment', 'error')
    return redirect(url_for('assignments'))


@app.route('/assignments/<assignment_id>/delete', methods=['POST'])
@admin_required
@csrf_check
def delete_assignment(assignment_id):
    if supabase.delete_assignment(assignment_id):
        flash('Assignment deleted', 'success')
    else:
        flash('Failed to delete assignment', 'error')
    return redirect(url_for('assignments'))


# ===================== CLIENTS (ADMIN - full visibility) =====================

@app.route('/clients')
@admin_required
def clients():
    clients_list = supabase.get_all_clients()
    offices = {o.id: o for o in supabase.get_all_offices()}
    return render_template('clients.html', clients=clients_list, offices=offices)


@app.route('/clients/create', methods=['POST'])
@admin_required
@csrf_check
def create_client():
    data = {
        'masked_identity': request.form.get('masked_identity', '').strip(),
        'real_identifier': request.form.get('real_identifier', '').strip(),
        'office_id': request.form.get('office_id') or None,
        'gateway_number': request.form.get('gateway_number', 'default').strip(),
        'platforms': request.form.getlist('platforms'),
        'platform_identifiers': {
            'telegram': request.form.get('telegram_identifier', '').strip(),
            'whatsapp': request.form.get('whatsapp_identifier', '').strip()
        }
    }
    if not data['masked_identity'] or not data['real_identifier']:
        flash('Masked identity and real identifier are required', 'error')
        return redirect(url_for('clients'))
    if not data['platforms']:
        flash('Select at least one approved platform', 'error')
        return redirect(url_for('clients'))
    result = supabase.create_client(data)
    if result:
        flash('Client created', 'success')
    else:
        flash('Failed to create client', 'error')
    return redirect(url_for('clients'))


@app.route('/clients/<client_id>/edit', methods=['POST'])
@admin_required
@csrf_check
def edit_client(client_id):
    data = {
        'masked_identity': request.form.get('masked_identity', '').strip(),
        'real_identifier': request.form.get('real_identifier', '').strip(),
        'office_id': request.form.get('office_id') or None,
        'gateway_number': request.form.get('gateway_number', 'default').strip(),
        'platforms': request.form.getlist('platforms'),
        'platform_identifiers': {
            'telegram': request.form.get('telegram_identifier', '').strip(),
            'whatsapp': request.form.get('whatsapp_identifier', '').strip()
        }
    }
    if not data['platforms']:
        flash('Select at least one approved platform', 'error')
        return redirect(url_for('clients'))
    if supabase.update_client(client_id, data):
        flash('Client updated', 'success')
    else:
        flash('Failed to update client', 'error')
    return redirect(url_for('clients'))


@app.route('/clients/<client_id>/delete', methods=['POST'])
@admin_required
@csrf_check
def delete_client(client_id):
    if supabase.delete_client(client_id):
        flash('Client deleted', 'success')
    else:
        flash('Failed to delete client', 'error')
    return redirect(url_for('clients'))


# ===================== OFFICES (Admin management) =====================

@app.route('/offices')
@admin_required
def offices():
    offices_list = supabase.get_all_offices()
    return render_template('offices.html', offices=offices_list)


@app.route('/offices/create', methods=['POST'])
@admin_required
@csrf_check
def create_office():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    if not name or not email or not password:
        flash('All fields are required', 'error')
        return redirect(url_for('offices'))
    data = {'name': name, 'email': email, 'password': password, 'is_active': True}
    result = supabase.create_office(data)
    if result:
        flash(f'Office {name} created', 'success')
        logger.info(f"Created office {name}")
    else:
        flash('Failed to create office', 'error')
    return redirect(url_for('offices'))


@app.route('/offices/<office_id>/edit', methods=['POST'])
@admin_required
@csrf_check
def edit_office(office_id):
    data = {
        'name': request.form.get('name', '').strip(),
        'email': request.form.get('email', '').strip(),
        'is_active': request.form.get('is_active') == 'on'
    }
    password = request.form.get('password', '').strip()
    if password:
        data['password'] = password
    if supabase.update_office(office_id, data):
        flash('Office updated', 'success')
    else:
        flash('Failed to update office', 'error')
    return redirect(url_for('offices'))


@app.route('/offices/<office_id>/delete', methods=['POST'])
@admin_required
@csrf_check
def delete_office(office_id):
    if supabase.delete_office(office_id):
        flash('Office deleted', 'success')
    else:
        flash('Failed to delete office', 'error')
    return redirect(url_for('offices'))


@app.route('/api/stats')
def api_stats():
    if is_admin():
        return jsonify(supabase.get_dashboard_stats())
    return jsonify({'error': 'unauthorized'}), 401
