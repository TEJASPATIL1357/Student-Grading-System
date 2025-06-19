from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import matplotlib.pyplot as plt
import os
from fpdf import FPDF
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
app.secret_key = 'your_secret_key'
def add_parent_email_column():
    with sqlite3.connect('students.db') as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN parent_email TEXT")
            print("✅ 'parent_email' column added successfully.")
        except sqlite3.OperationalError as e:
            print("ℹ️ Column may already exist or another error occurred:", e)

def create_db():
   with sqlite3.connect('students.db', timeout=10) as conn:
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT,
                 roll_number TEXT UNIQUE,
                 parent_email TEXT)''')    # Added parent_email here
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

    
    

create_db()

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    username = request.form['username']
    password = request.form['password']
    if username == "MLMALI" and password == "RCPIT":
        
        session['user'] = username
        return redirect(url_for('index'))
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        session['user'] = username
        return redirect(url_for('index'))
    return render_template('login.html', error="Invalid Credentials. Try Again!")

@app.route('/index')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('students.db')
    c = conn.cursor()
    c.execute("SELECT * FROM students")
    students = c.fetchall()
    conn.close()
    
    return render_template('index.html', user=session['user'], students=students)


@app.route('/add_student', methods=['POST'])
def add_student():
    name = request.form['name']
    roll_number = request.form['roll_number']
    parent_email = request.form['parent_email']
    try:
        with sqlite3.connect('students.db', timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO students (name, roll_number, parent_email) VALUES (?, ?, ?)", 
                      (name, roll_number, parent_email))
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
            c.execute("INSERT INTO grades (roll_number, subject, marks) VALUES (?, ?, ?)", (roll_number, subject, marks))
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
    
    # Prepare for frontend
    full_results = []
    for subject, marks in results:
        grade, remark = calculate_grade_and_remark(marks)
        full_results.append((subject, marks, grade, remark))
    
    # Chart
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
    student_name = c.fetchone()
    if student_name:
        student_name = student_name[0]
    else:
        student_name = "Unknown Student"

    c.execute("SELECT subject, marks FROM grades WHERE roll_number = ?", (roll_number,))
    results = c.fetchall()

    # Get parent email from DB
    c.execute("SELECT parent_email FROM students WHERE roll_number = ?", (roll_number,))
    email_receiver = c.fetchone()
    if email_receiver and email_receiver[0]:
        email_receiver = email_receiver[0]
    else:
        email_receiver = "monalpankajpatil@gmail.com"  # fallback

    conn.close()

    # Create PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.image('static/login-visual.png', x=10, y=8, w=30)  # adjust path and size as needed
    pdf.ln(20)  # add some space below the logo

    pdf.set_font("Arial", 'B', 24)
    pdf.cell(200, 10, txt=f"{student_name}'s Progress Report", ln=True, align='C')

    # Section 1: Table - Subject, Marks, Grade
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

    # Section 2: Feedback
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt=" Teacher Feedback", ln=True)
    pdf.set_font("Arial", '', 12)

    for line in feedback_lines:
        pdf.cell(0, 10, line, ln=True)

    # Insert chart image if exists
    chart_path = f'static/progress_{roll_number}.png'
    if os.path.exists(chart_path):
        pdf.ln(10)
        pdf.image(chart_path, x=30, w=150)

    # Save PDF
    pdf_file = f"progress_report_{roll_number}.pdf"
    pdf.output(pdf_file)

    # Email sending
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
    return redirect(url_for('login'))
if __name__ == '__main__':
    app.run(debug=True)



