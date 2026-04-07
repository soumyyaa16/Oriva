from flask import Flask, render_template, request, jsonify
import mysql.connector

app = Flask(__name__)

# Cloud database connection
def get_db():
    return mysql.connector.connect(
        host="maglev.proxy.rlwy.net",
        user="root",
        password="sqLmHxVyMBrVVfGqBfUckfszzExddlID",
        database="railway",
        port=47287
    )

@app.route('/')
def index():
    # Flask will now look for templates/index.html
    return render_template('index.html')

# ---- Patients ----
@app.route('/patients')
def get_patients():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM patient_risk_view ORDER BY risk_score DESC")
    patients = cursor.fetchall()
    db.close()
    return jsonify(patients)

@app.route('/patient/search')
def search_patient():
    name = request.args.get('name', '')
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM patient_risk_view 
        WHERE full_name LIKE %s 
        ORDER BY risk_score DESC
    """, (f'%{name}%',))
    patients = cursor.fetchall()
    db.close()
    return jsonify(patients)

@app.route('/patient/<int:patient_id>')
def get_patient(patient_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM patient_risk_view WHERE patient_id = %s", (patient_id,))
    patient = cursor.fetchone()

    cursor.execute("""
        SELECT pr.prescription_id, d.drug_name, d.brand_price, 
               d.generic_price, pr.dosage, pr.prescribed_date,
               doc.full_name as doctor_name
        FROM prescriptions pr
        JOIN drugs d ON pr.drug_id = d.drug_id
        JOIN doctors doc ON pr.doctor_id = doc.doctor_id
        WHERE pr.patient_id = %s
        ORDER BY pr.prescribed_date DESC
    """, (patient_id,))
    prescriptions = cursor.fetchall()

    cursor.execute("""
        SELECT a.alert_message, a.severity, a.alert_date
        FROM alerts a
        WHERE a.patient_id = %s
        ORDER BY a.alert_date DESC
    """, (patient_id,))
    alerts = cursor.fetchall()

    db.close()
    return jsonify({'patient': patient, 'prescriptions': prescriptions, 'alerts': alerts})

# ---- Register Patient ----
@app.route('/register_patient', methods=['POST'])
def register_patient():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO patients (full_name, age, gender, disease, comorbidities, oxygen_level, contact)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (data['full_name'], data['age'], data['gender'], data['disease'],
          data['comorbidities'], data['oxygen_level'], data['contact']))
    db.commit()
    patient_id = cursor.lastrowid
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM patient_risk_view WHERE patient_id = %s", (patient_id,))
    patient = cursor.fetchone()
    db.close()
    return jsonify({'status': 'success', 'patient': patient})

# ---- Drugs, Doctors, Alternatives, Alerts, etc ----
@app.route('/drugs')
def get_drugs():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM drugs ORDER BY drug_name")
    drugs = cursor.fetchall()
    db.close()
    return jsonify(drugs)

@app.route('/doctors')
def get_doctors():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM doctors ORDER BY full_name")
    doctors = cursor.fetchall()
    db.close()
    return jsonify(doctors)

# ---- Interactions, Prescriptions, Analytics ----
# (Keep all your existing routes here as in your original code)

if __name__ == '__main__':
    # On Render, debug=True is optional. 
    app.run(host='0.0.0.0', port=10000)