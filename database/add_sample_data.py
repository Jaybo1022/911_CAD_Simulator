import sqlite3
import os
from datetime import datetime, timedelta

def add_sample_data():
    """Add sample incidents and units for testing"""
    
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, "cad_simulator.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Clear existing sample units and add full fleet
        cursor.execute("DELETE FROM unit_personnel")
        cursor.execute("DELETE FROM units WHERE call_sign LIKE 'PAT-%' OR call_sign LIKE 'MED-%' OR call_sign LIKE 'ENG-%' OR call_sign LIKE 'LAD-%' OR call_sign LIKE 'RES-%' OR call_sign LIKE 'BC-%' OR call_sign LIKE 'QRV-%'")
        
        sample_units = []
        
        # Police: 3 districts x 4 zones x 2 shifts = 24 units
        # Districts: West (A), Central (B), East (C)
        # Zones: 1-4 per district
        # Shift: 1 = Day, 2 = Night
        districts = ['A', 'B', 'C']
        for district in districts:
            for zone in range(1, 5):
                for shift in [1, 2]:
                    sample_units.append((f"{district}{zone}{shift}", "Police Department", f"V-{3100 + len(sample_units)}", "Patrol", "AV"))
        
        # 8 ALS ambulances
        for i in range(1, 9):
            sample_units.append((f"MED-{i}", "EMS", f"V-{2000 + i}", "ALS Ambulance", "AV"))
        
        # 4 BLS ambulances
        for i in range(1, 5):
            sample_units.append((f"BLS-{i}", "EMS", f"V-{7000 + i}", "BLS Ambulance", "AV"))
        
        # 8 Engines
        for i in range(1, 9):
            sample_units.append((f"ENG-{i}", "Fire Department", f"V-{1000 + i}", "Engine", "AV"))
        
        # 6 Ladder trucks
        for i in range(1, 7):
            sample_units.append((f"LAD-{i}", "Fire Department", f"V-{4000 + i}", "Ladder", "AV"))
        
        # 4 Rescues
        for i in range(1, 5):
            sample_units.append((f"RES-{i}", "Fire Department", f"V-{5000 + i}", "Rescue", "AV"))
        
        # 1 Battalion Chief
        sample_units.append(("BC-1", "Fire Department", "V-9001", "Battalion Chief", "AV"))
        
        # 4 Quick Response Vehicles (optional) to round out EMS
        for i in range(1, 5):
            sample_units.append((f"QRV-{i}", "EMS", f"V-{6000 + i}", "QRV", "AV"))
        
        for call_sign, agency, vehicle, apparatus, status_code in sample_units:
            try:
                cursor.execute("""
                    INSERT INTO units (call_sign, agency, vehicle_number, apparatus_type, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (call_sign, agency, vehicle, apparatus, status_code, datetime.now(), datetime.now()))
                unit_id = cursor.lastrowid
                
                # Add sample personnel
                cursor.execute("""
                    INSERT INTO unit_personnel (unit_id, employee_number, assigned_at)
                    VALUES (?, ?, ?)
                """, (unit_id, f"EMP-{100 + unit_id}", datetime.now()))
            except sqlite3.IntegrityError:
                pass  # Unit already exists
        
        print(f"Added {len(sample_units)} sample units: 24 PD, 8 ALS, 4 BLS, 8 ENG, 6 LAD, 4 RES, 1 BC, 4 QRV")
        now = datetime.now()
        sample_incidents = [
            ("INC-2026-001", "Pending", 1, "Fire - Structure", "123 Main St", "Residential fire reported", "John Doe", "555-0101", now - timedelta(minutes=5), now - timedelta(minutes=5), None),
            ("INC-2026-002", "Dispatched", 2, "Medical - Cardiac", "456 Oak Ave", "Cardiac emergency", "Jane Smith", "555-0102", now - timedelta(minutes=15), now - timedelta(minutes=15), "MED-1"),
            ("INC-2026-003", "Active", 3, "Police - Traffic Stop", "789 Elm St", "Backup requested for traffic stop", "Officer Johnson", "555-0103", now - timedelta(minutes=25), now - timedelta(minutes=25), "A11"),
        ]
        
        incident_ids = {}  # Store incident IDs for unit assignment
        created_times = {}  # Store created times for audit trail
        
        for incident in sample_incidents:
            try:
                created_time = incident[8]  # created_at timestamp
                cursor.execute("""
                    INSERT INTO incidents (incident_number, status, priority_level, incident_type, location, description, caller_name, caller_phone, created_at, updated_at, dispatched_units)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, incident)
                incident_id = cursor.lastrowid
                incident_ids[incident[0]] = incident_id  # Store mapping
                created_times[incident[0]] = created_time  # Store created time
                
                # Add sample audit trail entries
                cursor.execute("""
                    INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (incident_id, "Incident Created", "911 call received and logged", "DISP-001", created_time))
                
                if incident[1] == "Dispatched":
                    cursor.execute("""
                        INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    """, (incident_id, "Status Change", "Incident status changed to Dispatched", "DISP-001", created_time + timedelta(minutes=2)))
                
            except sqlite3.IntegrityError:
                pass  # Incident already exists - skip unit assignment for existing incidents
                # Remove from incident_ids if it wasn't created
                if incident[0] in incident_ids:
                    del incident_ids[incident[0]]
        
        # Assign units to incidents (only for newly created incidents)
        # Assign MED-1 to INC-2026-002
        if incident_ids.get("INC-2026-002"):
            cursor.execute("UPDATE units SET current_incident_id = ? WHERE call_sign = ?", 
                          (incident_ids.get("INC-2026-002"), "MED-1"))
        
        # Assign A11 to INC-2026-003
        if incident_ids.get("INC-2026-003"):
            cursor.execute("UPDATE units SET current_incident_id = ? WHERE call_sign = ?", 
                          (incident_ids.get("INC-2026-003"), "A11"))
        
        conn.commit()
        print("Sample data added successfully!")
        print("Added 59 sample units and 3 sample incidents")
        print("Units assigned to incidents for testing")
        
    except Exception as e:
        conn.rollback()
        print(f"Error adding sample data: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_sample_data()
