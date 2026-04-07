from flask import Flask, render_template, request, jsonify
import mysql.connector

app = Flask(__name__)

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
    return render_template('index.html')

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

@app.route('/drugs')
def get_drugs():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM drugs ORDER BY drug_name")
    drugs = cursor.fetchall()
    db.close()
    return jsonify(drugs)

@app.route('/drugs/search')
def search_drugs():
    name = request.args.get('name', '')
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM drugs WHERE drug_name LIKE %s", (f'%{name}%',))
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

@app.route('/check_interaction', methods=['POST'])
def check_interaction():
    data = request.json
    patient_id = data['patient_id']
    drug_id = data['drug_id']
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            d1.drug_name as drug1,
            d2.drug_name as drug2,
            di.severity,
            di.interaction_effect,
            alt.drug_name as alternative,
            a.reason_for_switch,
            CONCAT('Rs. ', orig.brand_price) as current_cost,
            CONCAT('Rs. ', alt.generic_price) as alternative_cost,
            CONCAT(ROUND(((orig.brand_price - alt.generic_price) / orig.brand_price) * 100, 1), '%') as savings
        FROM drug_interactions di
        JOIN drugs d1 ON di.drug1_id = d1.drug_id
        JOIN drugs d2 ON di.drug2_id = d2.drug_id
        LEFT JOIN alternatives a ON a.drug_id = di.drug1_id OR a.drug_id = di.drug2_id
        LEFT JOIN drugs alt ON a.alternative_drug_id = alt.drug_id
        LEFT JOIN drugs orig ON orig.drug_id = a.drug_id
        WHERE (di.drug1_id = %s OR di.drug2_id = %s)
        AND (
            di.drug1_id IN (SELECT drug_id FROM prescriptions WHERE patient_id = %s)
            OR
            di.drug2_id IN (SELECT drug_id FROM prescriptions WHERE patient_id = %s)
        )
        LIMIT 1
    """, (drug_id, drug_id, patient_id, patient_id))

    interaction = cursor.fetchone()
    db.close()
    return jsonify({'interaction': interaction})

@app.route('/add_prescription', methods=['POST'])
def add_prescription():
    data = request.json
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        CALL AddPrescription(%s, %s, %s, %s, %s)
    """, (data['patient_id'], data['doctor_id'], data['drug_id'], data['dosage'], data['date']))

    db.commit()
    db.close()
    return jsonify({'status': 'success'})

@app.route('/alerts')
def get_alerts():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.full_name, a.alert_message, a.severity, a.alert_date
        FROM alerts a
        JOIN patients p ON a.patient_id = p.patient_id
        ORDER BY a.alert_date DESC
    """)

    alerts = cursor.fetchall()
    db.close()
    return jsonify(alerts)

@app.route('/alternatives')
def get_alternatives():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            p.full_name AS patient_name,
            d.drug_name AS dangerous_drug,
            alt.drug_name AS safer_alternative,
            a.reason_for_switch,
            CONCAT('Rs. ', d.brand_price) AS current_cost,
            CONCAT('Rs. ', alt.generic_price) AS alternative_cost,
            CONCAT(ROUND(((d.brand_price - alt.generic_price) / d.brand_price) * 100, 1), '%') AS savings
        FROM alternatives a
        JOIN drugs d ON a.drug_id = d.drug_id
        JOIN drugs alt ON a.alternative_drug_id = alt.drug_id
        JOIN prescriptions pr ON pr.drug_id = a.drug_id
        JOIN patients p ON pr.patient_id = p.patient_id
        ORDER BY d.brand_price DESC
    """)

    alternatives = cursor.fetchall()
    db.close()
    return jsonify(alternatives)

@app.route('/check-drugs')
def check_drugs():
    drug1 = request.args.get('drug1', '').strip().lower()
    drug2 = request.args.get('drug2', '').strip().lower()
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT di.interaction_effect as description
        FROM drug_interactions di
        JOIN drugs d1 ON di.drug1_id = d1.drug_id
        JOIN drugs d2 ON di.drug2_id = d2.drug_id
        WHERE (LOWER(d1.drug_name) LIKE %s AND LOWER(d2.drug_name) LIKE %s)
        OR (LOWER(d1.drug_name) LIKE %s AND LOWER(d2.drug_name) LIKE %s)
        LIMIT 1
    """, (f'%{drug1}%', f'%{drug2}%', f'%{drug2}%', f'%{drug1}%'))

    result = cursor.fetchone()
    db.close()

    if result:
        return jsonify({'interaction': True, 'description': result['description']})
    else:
        return jsonify({'interaction': False})

@app.route('/analytics')
def get_analytics():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT risk_level, COUNT(*) as count 
        FROM patient_risk_view 
        GROUP BY risk_level
    """)
    risk_dist = cursor.fetchall()

    cursor.execute("""
        SELECT d.drug_name, COUNT(*) as interaction_count
        FROM drug_interactions di
        JOIN drugs d ON di.drug1_id = d.drug_id OR di.drug2_id = d.drug_id
        GROUP BY d.drug_name
        ORDER BY interaction_count DESC
        LIMIT 8
    """)
    dangerous_drugs = cursor.fetchall()

    cursor.execute("""
        SELECT 
            p.full_name,
            ROUND(((d.brand_price - alt.generic_price) / d.brand_price) * 100, 1) as saving_pct
        FROM alternatives a
        JOIN drugs d ON a.drug_id = d.drug_id
        JOIN drugs alt ON a.alternative_drug_id = alt.drug_id
        JOIN prescriptions pr ON pr.drug_id = a.drug_id
        JOIN patients p ON pr.patient_id = p.patient_id
        ORDER BY saving_pct DESC
        LIMIT 8
    """)
    savings = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total FROM alerts WHERE severity = 'HIGH'")
    high_alerts = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as total FROM alerts WHERE severity = 'MODERATE'")
    mod_alerts = cursor.fetchone()

    cursor.execute("""
        SELECT doc.full_name, COUNT(*) as total_prescriptions
        FROM prescriptions pr
        JOIN doctors doc ON pr.doctor_id = doc.doctor_id
        GROUP BY doc.full_name
        ORDER BY total_prescriptions DESC
        LIMIT 8
    """)
    doctor_stats = cursor.fetchall()

    db.close()

    return jsonify({
        'risk_distribution': risk_dist,
        'dangerous_drugs': dangerous_drugs,
        'savings': savings,
        'high_alerts': high_alerts['total'],
        'moderate_alerts': mod_alerts['total'],
        'doctor_stats': doctor_stats
    })

if __name__ == '__main__':
    app.run(debug=True)