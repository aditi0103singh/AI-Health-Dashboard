import os
import sqlite3
from flask import Flask, render_template, request, redirect, flash, url_for
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. Force absolute path lookup for the environment configuration file
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=env_path, override=True)

app = Flask(__name__)
app.secret_key = "mira_intelligence_secure_key"

# 2. Extract and strictly validate the parsed token key string
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    # Diagnostic fallback check if configuration file string matching fails
    raise ValueError(
        f"CRITICAL ERROR: System failed to locate 'GEMINI_API_KEY' in configuration file layout.\n"
        f"Expected location: {env_path}\n"
        f"Please verify the file name begins with a dot and contains no spacing rules around the '=' sign."
    )

client = genai.Client(api_key=api_key)
MODEL_NAME = 'gemini-2.5-flash'

# -------------------------------------------------------------------------
# DATABASE ENGINE FUNCTIONS
# -------------------------------------------------------------------------
def get_db_connection():
    """Establishes database connection with standard Row Factory optimization."""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # Essential for p['column_name'] syntax matching
    return conn

def init_db():
    """Generates schema configuration structure on startup if missing."""
    with get_db_connection() as conn:
        # We use explicit unrestricted TEXT fields to allow unlimited remarks storage space
        conn.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                dob TEXT NOT NULL,
                email TEXT NOT NULL,
                glucose REAL NOT NULL,
                haemoglobin REAL NOT NULL,
                cholesterol REAL NOT NULL,
                remarks TEXT NOT NULL
            )
        ''')
        conn.commit()

# -------------------------------------------------------------------------
# CORE AI CLINICAL DIAGNOSTICS GENERATOR
# -------------------------------------------------------------------------
def get_ai_analysis(glucose, hb, cholesterol):
    """Processes biometric tokens via Gemini, featuring an immediate local mock-engine bypass for 503 spikes."""
    global api_key
    if not api_key or api_key.strip() == "":
        return "System Configuration Alert: The GEMINI_API_KEY environment variable is empty or unreadable."

    # Construct the clinical evaluation parameters
    prompt = f"""
    You are a clinical assistant. Analyze these patient metrics:
    - Glucose: {glucose} mg/dL
    - Haemoglobin (Hb): {hb} g/dL
    - Cholesterol: {cholesterol} mg/dL

    INSTRUCTIONS:
    1. Keep your analysis concise, aiming for a single focused paragraph (around 3 to 5 sentences). 
    2. CRITICAL: Never stop mid-sentence. Ensure your final thoughts are completely closed with a period.
    3. Do not use markdown bold symbols (**), bullet points, or intros.
    4. Never use math symbols like '<' or '>'. Use words like "less than" or "above".
    5. DISEASE NAME: Explicitly state the clinical name of any condition found.
    6. ETIOLOGY: Briefly explain why the condition is caused in simple language for the patient.
    7. If everything is normal, output: "Normal Metabolic Profile. All blood markers look perfectly balanced and healthy."
    """

    # 1. Try Primary Model (Gemini 2.5 Flash)
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=800)
        )
        if response and response.text:
            return response.text.strip().replace("**", "")

    except Exception as primary_error:
        print(f"Primary model unavailable, attempting backup endpoint... Details: {str(primary_error)}")
        
        # 2. Try Secondary Model (Gemini 2.5 Flash-Lite)
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=800)
            )
            if response and response.text:
                return response.text.strip().replace("**", "") + " (Evaluated via MIRA Backup Engine)"
        
        except Exception as fallback_error:
            print(f"Cloud clusters overloaded. Activating MIRA Local Clinical Engine Fallback...")
            
            # 3. LOCAL INTELLIGENCE BYPASS: Generates authentic clinical text locally if cloud is totally down
            conditions = []
            explanations = []
            
            if glucose > 125.0:
                conditions.append("Hyperglycemia")
                explanations.append("high blood sugar indicates your body is struggling to process glucose efficiently due to insulin resistance")
            elif glucose < 70.0:
                conditions.append("Hypoglycemia")
                explanations.append("critically low glucose means your cells are starved of their primary operational energy source")
            elif 100.0 <= glucose <= 125.0:
                conditions.append("Prediabetes")
                explanations.append("impaired fasting glucose indicates your blood sugar is higher than baseline normal but manageable through lifestyle changes")
                
            if hb < 12.0:
                conditions.append("Anemia")
                explanations.append("low hemoglobin indicates a drop in healthy red blood cells, which limits oxygen delivery across vital tissue groups")
                
            if cholesterol > 240.0:
                conditions.append("Hypercholesterolemia")
                explanations.append("elevated lipid profiles signify a high concentration of fatty deposits inside your bloodstream, which increases cardiovascular strain")

            if conditions:
                disease_str = " and ".join(conditions)
                detail_str = ", while ".join(explanations)
                return (
                    f"The patient's clinical profile indicates an active state of {disease_str}. "
                    f"This occurs because {detail_str}. Immediate medical evaluation, structured dietary monitoring, "
                    f"and regular physician consultations are highly recommended to stabilize these metabolic parameters safely. (MIRA Local Fallback Mode)"
                )
            
            return "Normal Metabolic Profile. All blood markers look perfectly balanced and healthy. (MIRA Local Fallback Mode)"

    return "MIRA Analysis Pending: Empty response received from the evaluation engine cluster."
# -------------------------------------------------------------------------
# WEB APP INTERACTION ROUTES
# -------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def dashboard():
    """Handles intake entries processing and root dashboard rendering."""
    if request.method == "POST":
        fullname = request.form["fullname"]
        dob = request.form["dob"]
        email = request.form["email"]
        glucose = float(request.form["glucose"])
        haemoglobin = float(request.form["haemoglobin"])
        cholesterol = float(request.form["cholesterol"])

        # Compute clinical intelligence via Gemini Engine
        remarks = get_ai_analysis(glucose, haemoglobin, cholesterol)

        # Record mapping registration to database storage
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO patients (fullname, dob, email, glucose, haemoglobin, cholesterol, remarks)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (fullname, dob, email, glucose, haemoglobin, cholesterol, remarks))
            conn.commit()

        flash("Patient entry registered and evaluated by MIRA Engine successfully!", "success")
        return redirect(url_for("dashboard"))

    # Fetch all records to display in frontend directory table layout
    with get_db_connection() as conn:
        patients = conn.execute("SELECT * FROM patients ORDER BY id DESC").fetchall()
    
    return render_template("index.html", patients=patients)


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    """Processes pipeline updates, triggering AI evaluation recalculations on save."""
    conn = get_db_connection()
    patient = conn.execute("SELECT * FROM patients WHERE id = ?", (id,)).fetchone()

    if not patient:
        conn.close()
        flash("Target record resource not discovered.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        fullname = request.form["fullname"]
        dob = request.form["dob"]
        email = request.form["email"]
        glucose = float(request.form["glucose"])
        haemoglobin = float(request.form["haemoglobin"])
        cholesterol = float(request.form["cholesterol"])

        # Re-run diagnostic evaluation processing on updated biometric data values
        new_remarks = get_ai_analysis(glucose, haemoglobin, cholesterol)

        conn.execute('''
            UPDATE patients
            SET fullname=?, dob=?, email=?, glucose=?, haemoglobin=?, cholesterol=?, remarks=?
            WHERE id=?
        ''', (fullname, dob, email, glucose, haemoglobin, cholesterol, new_remarks, id))
        conn.commit()
        conn.close()

        flash("Patient file updated and diagnostic summaries re-evaluated!", "info")
        return redirect(url_for("dashboard"))

    conn.close()
    return render_template("edit.html", patient=patient)


@app.route("/delete/<int:id>")
def delete(id):
    """Purges target clinical profiles permanently out of persistent memory storage."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM patients WHERE id = ?", (id,))
        conn.commit()
    
    flash("Patient profile safely purged from database directory.", "warning")
    return redirect(url_for("dashboard"))

# -------------------------------------------------------------------------
# SYSTEM EXECUTION BOUNDARY
# -------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()  # Verifies local storage state structure setup configurations
    print("MIRA System Initialization Sequence Complete. Launching Dashboard Engine...")
    app.run(debug=True)