from flask import session as flask_session, redirect, url_for, abort
from functools import wraps

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_name' not in flask_session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not flask_session.get('is_admin'):
            abort(403)
        return f(*args, **kwargs)
    return wrapper
