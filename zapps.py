# -*- coding: utf-8 -*-
"""
Created on Sun Mar  2 16:19:14 2025

@author: amine
"""

# app.py
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.api import FacebookAdsApi
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import json
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuration
class Config:
    FACEBOOK_APP_ID = "VOTRE_APP_ID"
    FACEBOOK_APP_SECRET = "VOTRE_APP_SECRET"
    DATABASE = "users.db"

app.config.from_object(Config)

# Base de données SQLite pour les utilisateurs
def init_db():
    with sqlite3.connect(Config.DATABASE) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        conn.commit()

# Modèle User pour Flask-Login
class User(UserMixin):
    def __init__(self, id, username, is_admin=False):
        self.id = id
        self.username = username
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect(Config.DATABASE) as conn:
        c = conn.cursor()
        user = c.execute('SELECT id, username, is_admin FROM users WHERE id = ?', (user_id,)).fetchone()
        if user:
            return User(user[0], user[1], bool(user[2]))
    return None

# Décorateur pour les routes admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Accès refusé. Privilèges administrateur requis.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Routes d'authentification
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        with sqlite3.connect(Config.DATABASE) as conn:
            c = conn.cursor()
            user_data = c.execute('SELECT id, username, password_hash, is_admin FROM users WHERE username = ?', 
                                (username,)).fetchone()
            
            if user_data and check_password_hash(user_data[2], password):
                user = User(user_data[0], user_data[1], bool(user_data[3]))
                login_user(user)
                return redirect(url_for('index'))
            
            flash('Identifiants invalides', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        with sqlite3.connect(Config.DATABASE) as conn:
            c = conn.cursor()
            if c.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone():
                flash('Nom d\'utilisateur déjà pris', 'error')
            else:
                password_hash = generate_password_hash(password)
                c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                         (username, password_hash))
                conn.commit()
                flash('Inscription réussie, vous pouvez maintenant vous connecter', 'success')
                return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Route principale protégée
@app.route('/')
@login_required
def index():
    return render_template('index.html')

#[... Reste des fonctions de vérification des liens et API Facebook inchangées ...]

# Route admin pour gérer les utilisateurs
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    with sqlite3.connect(Config.DATABASE) as conn:
        c = conn.cursor()
        users = c.execute('SELECT id, username, is_admin FROM users').fetchall()
    return render_template('admin_users.html', users=users)

if __name__ == '__main__':
    try:
        init_db()
        app.run(debug=True, use_reloader=False)
    except Exception as e:
        import traceback
        print("Une erreur est survenue :")
        traceback.print_exc()