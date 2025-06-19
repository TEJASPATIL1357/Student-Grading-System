from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import matplotlib.pyplot as plt
import os
from fpdf import FPDF
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def create_db():
    with sqlite3.connect('students.db', timeout=10) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS students (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     name TEXT,
                     roll_number TEXT UNIQUE,
                     parent_email TEXT,
                     user_id INTEGER)''')  # ✅ Added user_id
        c.execute('''CREATE TABLE IF NOT EXISTS grades (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     roll_number TEXT,
                     subject TEXT,
                     marks INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     username TEXT UNIQUE,
                     password TEXT)''')
        conn.commit()

def add_user_id_column():
    with sqlite3.connect('students.db') as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN user_id INTEGER")
            print("✅ 'user_id' column added to students table.")
        except sqlite3.OperationalError:
            pass  # Column already exists

create_db()
add_user_id_column()

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    username = request.form['username']
    password = request.form['password']
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        session['user'] = username
        session['user_id'] = user[0]
        return redirect(url_for('index'))
    return render_template('login.html', error="Invalid Credentials. Try Again!")

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register_post():
    username = request.form['username']
    password = request.form['password']
    try:
        with sqlite3.connect('students.db') as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        return redirect(url_for('login'))
    except:
        return render_template('register.html', error="User already exists!")

@app.route('/index')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE user_id = ?", (user_id,))
    students = c.fetchall()
    conn.close()
    return render_template('index.html', user=session['user'], students=students)

@app.route('/add_student', methods=['POST'])
def add_student():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    name = request.form['name']
    roll_number = request.form['roll_number']
    parent_email = request.form['parent_email']
    user_id = session['user_id']
    try:
        with sqlite3.connect('students.db', timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO students (name, roll_number, parent_email, user_id) VALUES (?, ?, ?, ?)", 
                      (name, roll_number, parent_email, user_id))
            conn.commit()
    except sqlite3.OperationalError as e:
        return f"Database error: {e}"
    return redirect(url_for('index'))

@app.route('/grade', methods=['POST'])
def add_grade():
    roll_number = request.form['roll_number']
    subject = request.form['subject']
    marks = int(request.form['marks'])
    try:
        with sqlite3.connect('students.db', timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO grades (roll_number, subject, marks) VALUES (?, ?, ?)", 
                      (roll_number, subject, marks))
            conn.commit()
    except sqlite3.OperationalError as e:
        return f"Database error: {e}"
    return redirect(url_for('index'))

def calculate_grade_and_remark(marks):
    if marks >= 90:
        return 'A+', 'Excellent'
    elif marks >= 75:
        return 'A', 'Good'
    elif marks >= 60:
        return 'B', 'Average'
    else:
        return 'C', 'Needs Improvement'

@app.route('/progress', methods=['POST'])
def progress():
    roll_number = request.form['roll_number']
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    c.execute("SELECT subject, marks FROM grades WHERE roll_number = ?", (roll_number,))
    results = c.fetchall()
    conn.close()

    full_results = []
    for subject, marks in results:
        grade, remark = calculate_grade_and_remark(marks)
        full_results.append((subject, marks, grade, remark))

    subjects = [row[0] for row in results]
    marks = [row[1] for row in results]

    plt.figure(figsize=(8,5))
    plt.bar(subjects, marks, color='skyblue')
    plt.xlabel('Subjects')
    plt.ylabel('Marks')
    plt.title(f'Progress Chart for {roll_number}')
    chart_path = f'static/progress_{roll_number}.png'
    plt.savefig(chart_path)
    plt.close()

    return render_template('progress.html', roll_number=roll_number, results=full_results, chart_path=chart_path)

@app.route('/send_report', methods=['POST'])
def send_report():
    roll_number = request.form['roll_number']
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    c.execute("SELECT name FROM students WHERE roll_number = ?", (roll_number,))
    student_name = c.fetchone()[0]

    c.execute("SELECT subject, marks FROM grades WHERE roll_number = ?", (roll_number,))
    results = c.fetchall()

    c.execute("SELECT parent_email FROM students WHERE roll_number = ?", (roll_number,))
    email_receiver = c.fetchone()[0]

    conn.close()

    pdf = FPDF()
    pdf.add_page()
    pdf.image('static/login-visual.png', x=10, y=8, w=30)
    pdf.ln(20)
    pdf.set_font("Arial", 'B', 24)
    pdf.cell(200, 10, txt=f"{student_name}'s Progress Report", ln=True, align='C')

    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt=" Academic Performance", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(60, 10, "Subject", 1)
    pdf.cell(40, 10, "Marks", 1)
    pdf.cell(80, 10, "Grade", 1)
    pdf.ln()

    feedback_lines = []
    for subject, marks in results:
        if marks >= 70:
            grade = "Excellent"
        elif marks >= 40:
            grade = "Average"
        else:
            grade = "Needs Improvement"
        feedback_lines.append(f"{subject}: {grade}")
        pdf.cell(60, 10, subject, 1)
        pdf.cell(40, 10, str(marks), 1)
        pdf.cell(80, 10, grade, 1)
        pdf.ln()

    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt=" Teacher Feedback", ln=True)
    pdf.set_font("Arial", '', 12)
    for line in feedback_lines:
        pdf.cell(0, 10, line, ln=True)

    chart_path = f'static/progress_{roll_number}.png'
    if os.path.exists(chart_path):
        pdf.ln(10)
        pdf.image(chart_path, x=30, w=150)

    pdf_file = f"progress_report_{roll_number}.pdf"
    pdf.output(pdf_file)

    email_sender = "tp257188@gmail.com"
    email_password = "tlxs eipb owle apgu"

    msg = EmailMessage()
    msg['Subject'] = f"{student_name}'s Progress Report"
    msg['From'] = email_sender
    msg['To'] = email_receiver
    msg.set_content(f"Attached is the progress report for {student_name} (Roll No: {roll_number}).")

    with open(pdf_file, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=pdf_file)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(email_sender, email_password)
        server.send_message(msg)

    os.remove(pdf_file)
    return render_template('success.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
