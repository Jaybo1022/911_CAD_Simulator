import sqlite3
import os
from datetime import datetime

def initialize_database():
    """Initialize the CAD Simulator SQLite database with all required tables"""
    
    # Ensure database directory exists
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, "cad_simulator.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Units table - Active units on duty
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_sign TEXT UNIQUE NOT NULL,
            agency TEXT NOT NULL,
            vehicle_number TEXT,
            apparatus_type TEXT,
            status TEXT DEFAULT 'Available',
            current_incident_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Unit Personnel table - Personnel assigned to units
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unit_personnel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER NOT NULL,
            employee_number TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE
        )
    """)
    
    # Incidents table - Active and cleared incidents
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_number TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'Pending',
            priority_level INTEGER DEFAULT 3,
            incident_type TEXT,
            location TEXT,
            common_place TEXT,
            description TEXT,
            caller_name TEXT,
            caller_phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            dispatched_units TEXT,
            disposition_code TEXT,
            disposition_notes TEXT
        )
    """)

    # Ensure common_place column exists for older databases
    try:
        cursor.execute("ALTER TABLE incidents ADD COLUMN common_place TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise
    
    # Incident Audit Trail table - Timestamped log of incident actions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incident_audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            user_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
        )
    """)
    
    # Shift History table - Historical record of unit shifts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_sign TEXT NOT NULL,
            agency TEXT NOT NULL,
            vehicle_number TEXT,
            apparatus_type TEXT,
            personnel_list TEXT,
            status TEXT,
            shift_start TIMESTAMP NOT NULL,
            shift_end TIMESTAMP NOT NULL,
            incidents_handled INTEGER DEFAULT 0,
            total_response_time INTEGER DEFAULT 0
        )
    """)
    
    # Location Call History table - Historical calls by location
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS location_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            incident_id INTEGER,
            call_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            incident_type TEXT,
            frequency INTEGER DEFAULT 1,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        )
    """)
    
    # Hazard Alerts table - Known hazards for locations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hazard_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            hazard_type TEXT NOT NULL,
            description TEXT,
            severity_level INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    """)
    
    # Run Cards table - Standard response requirements by incident type
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS run_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            incident_type TEXT NOT NULL,
            required_units TEXT NOT NULL,
            priority_level INTEGER DEFAULT 3,
            additional_notes TEXT
        )
    """)
    
    # Vehicle Tools table - Equipment available by vehicle type
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_tools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_type TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            description TEXT
        )
    """)
    
    # Subject Tools table - Subject-related resources and protocols
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subject_tools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL,
            protocol_name TEXT NOT NULL,
            description TEXT,
            priority_level INTEGER DEFAULT 3
        )
    """)
    
    # Trainees table - User profile management
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trainees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            badge_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    """)
    
    # Evaluation Sessions table - Training session tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trainee_id INTEGER NOT NULL,
            scenario_name TEXT NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            status TEXT DEFAULT 'active',
            total_score REAL,
            FOREIGN KEY (trainee_id) REFERENCES trainees(id)
        )
    """)
    
    # Scenario Timelines table - Trigger events for scenarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scenario_timelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_name TEXT NOT NULL,
            trigger_time_seconds INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            is_processed BOOLEAN DEFAULT 0
        )
    """)
    
    # Evaluation Metrics table - Performance tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            metric_type TEXT NOT NULL,
            expected_value TEXT,
            actual_value TEXT,
            is_correct BOOLEAN,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES evaluation_sessions(id)
        )
    """)
    
    # Session Audit Trail table - Session event logging
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES evaluation_sessions(id)
        )
    """)
    
    # NCIC Vehicle Queries table - Vehicle query results linked to incidents
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ncic_vehicle_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            plate_number TEXT NOT NULL,
            state TEXT NOT NULL,
            registration_status TEXT,
            year TEXT,
            make TEXT,
            model TEXT,
            vin TEXT,
            stolen_status TEXT,
            query_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
        )
    """)
    
    # NCIC Subject Queries table - Person query results linked to incidents
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ncic_subject_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            first_name TEXT,
            last_name TEXT,
            dob TEXT,
            dl_number TEXT,
            dl_state TEXT,
            race TEXT,
            sex TEXT,
            height TEXT,
            weight TEXT,
            license_status TEXT,
            warrants TEXT,
            query_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_units_status ON units(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_priority ON incidents(priority_level)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trail_incident ON incident_audit_trail(incident_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_location_history_location ON location_history(location)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hazard_alerts_location ON hazard_alerts(location)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ncic_vehicle_incident ON ncic_vehicle_queries(incident_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ncic_subject_incident ON ncic_subject_queries(incident_id)")
    
    # Insert sample run cards
    sample_run_cards = [
        ("Fire - Structure", "Engine:2, Ladder:1, Battalion:1", 1, "Standard structure fire response"),
        ("Fire - Vehicle", "Engine:1, Rescue:1", 2, "Vehicle fire response"),
        ("Medical - Cardiac", "Medic:1, Engine:1", 1, "Cardiac emergency response"),
        ("Medical - Trauma", "Medic:1, Rescue:1", 1, "Trauma response"),
        ("Police - Domestic", "Patrol:2", 2, "Domestic disturbance response"),
        ("Police - Traffic Stop", "Patrol:1", 3, "Routine traffic stop backup"),
        ("MVA - Injury", "Medic:1, Rescue:1, Police:1", 1, "Motor vehicle accident with injuries"),
        ("MVA - No Injury", "Police:1", 3, "Motor vehicle accident without injuries"),
    ]
    
    for card in sample_run_cards:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO run_cards (incident_type, required_units, priority_level, additional_notes)
                VALUES (?, ?, ?, ?)
            """, card)
        except sqlite3.IntegrityError:
            pass  # Ignore if already exists
    
    # Insert sample vehicle tools
    sample_vehicle_tools = [
        ("Engine", "Hose Line", 3, "Attack lines for fire suppression"),
        ("Engine", "Water Tank", 1, "Primary water supply"),
        ("Engine", "Pump", 1, "Water pumping apparatus"),
        ("Ladder", "Aerial Device", 1, "Elevated platform"),
        ("Ladder", "Ground Ladders", 4, "Portable ladders"),
        ("Medic", "AED", 1, "Automated external defibrillator"),
        ("Medic", "Oxygen Kit", 2, "Medical oxygen supply"),
        ("Medic", "Trauma Kit", 1, "Emergency medical supplies"),
        ("Rescue", "Jaws of Life", 1, "Extrication tool"),
        ("Rescue", "Air Bags", 2, "Lifting equipment"),
        ("Patrol", "First Aid Kit", 1, "Basic medical supplies"),
        ("Patrol", "Traffic Cones", 6, "Traffic control"),
    ]
    
    for tool in sample_vehicle_tools:
        cursor.execute("""
            INSERT INTO vehicle_tools (vehicle_type, tool_name, quantity, description)
            VALUES (?, ?, ?, ?)
        """, tool)
    
    # Insert sample subject tools
    sample_subject_tools = [
        ("Cardiac Patient", "CPR Protocol", "Immediate CPR if no pulse", 1),
        ("Cardiac Patient", "AED Protocol", "Deploy AED as soon as available", 1),
        ("Diabetic", "Glucose Check", "Check blood glucose levels", 2),
        ("Diabetic", "Oral Glucose", "Administer if conscious and low glucose", 2),
        ("Trauma Patient", "Spinal Precaution", "Immobilize spine if mechanism suggests", 1),
        ("Trauma Patient", "Bleeding Control", "Apply direct pressure to bleeding sites", 1),
        ("Respiratory Distress", "Oxygen Therapy", "Administer oxygen per protocol", 2),
        ("Respiratory Distress", "Airway Management", "Monitor and maintain airway", 1),
    ]
    
    for tool in sample_subject_tools:
        cursor.execute("""
            INSERT INTO subject_tools (subject_type, protocol_name, description, priority_level)
            VALUES (?, ?, ?, ?)
        """, tool)
    
    conn.commit()
    conn.close()
    
    print(f"Database initialized successfully at: {db_path}")
    print("Tables created: units, unit_personnel, incidents, incident_audit_trail, shift_history, location_history, hazard_alerts, run_cards, vehicle_tools, subject_tools")
    print("Sample data inserted for run cards, vehicle tools, and subject tools")

if __name__ == "__main__":
    initialize_database()
