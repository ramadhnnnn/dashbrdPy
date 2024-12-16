from flask import Flask, render_template, redirect, request, url_for, session, flash
from extensions import mysql  # Import MySQL dari extensions.py
from config import Config # Import konfigurasi dari config.py
import bcrypt
from main import main_bp  # Import blueprint dari main.py
from dashboard import dashboard_bp #import bluprint dari dashboard.py

def create_app():
    app = Flask(__name__)

    # Load konfigurasi dari config.py
    app.config.from_object(Config)

    # Inisialisasi MySQL dengan app setelah app diinisialisasi
    mysql.init_app(app)

    # Register Blueprint
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)

    return app

# Inisialisasi aplikasi menggunakan factory function
app = create_app()

# Route untuk Home, Signup, Login, dll.
@app.route('/')
def home():
    return render_template("sign-in.html")

@app.route('/signup', methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("sign-up.html")
    else:
        try:
            email = request.form['email']
            name = request.form['name']
            password = request.form['password'].encode('utf-8')
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM user WHERE Email = %s", (email,))
            existing_user = cur.fetchone()

            if existing_user:
                flash('Email is already registered. Please use a different email.', 'error')
                return redirect(url_for('register'))
            else:
                hash_password = bcrypt.hashpw(password, bcrypt.gensalt())
                cur.execute("INSERT INTO user (Email, Name, password) VALUES (%s, %s, %s)", (email, name, hash_password))
                mysql.connection.commit()
                cur.close()

                session['email'] = email
                return redirect(url_for('login'))

        except Exception as e:
            print(f"Error inserting data: {str(e)}")
            return f"An error occurred: {str(e)}"

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("sign-in.html")
    else:
        email = request.form['email']
        password = request.form['password'].encode('utf-8')

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM user WHERE Email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
            session['email'] = user['Email']
            return redirect(url_for('main_bp.inventory'))
        else:
            flash('Invalid email or password. Please try again.', 'error')
            return redirect(url_for('login'))

@app.route('/enteremail', methods=['GET', 'POST'])
def enter_email():
    if request.method == 'POST':
        email = request.form['email']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM user WHERE Email = %s", [email])
        user = cur.fetchone()
        cur.close()

        if user:
            session['email'] = email
            return redirect(url_for('new_password'))
        else:
            return redirect(url_for('enter_email'))
    return render_template('enter-email.html')

@app.route('/check-email')
def check_email():
    return render_template('check-email.html')

@app.route('/new-password', methods=['GET', 'POST'])
def new_password():
    if request.method == 'GET':
        return render_template('new-password.html')
    elif request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        if new_password == confirm_password:
            hash_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            cur = mysql.connection.cursor()
            cur.execute("UPDATE user SET password = %s WHERE Email = %s", (hash_password, session['email']))
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('success_reset_password'))
        else:
            return redirect(url_for('new_password'))

@app.route('/success-reset-password')
def success_reset_password():
    return render_template('success-reset-password.html')

# Jalankan aplikasi
if __name__ == '__main__':
    app.run(debug=True, port=5001)
