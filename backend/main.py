from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from typing import Optional, List
import os
from dotenv import load_dotenv
import openai
from datetime import datetime
import sqlite3
import json
import asyncio

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    groq_api_key: str = os.getenv("GROQ_API_KEY")
    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    database_path: str = "database/cad_simulator.db"

settings = Settings()

app = FastAPI(title="911 CAD Simulator", description="Dispatcher Training Simulation System")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database connection helper
def get_db_connection():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    return conn

# Pydantic models
class OnDutyRequest(BaseModel):
    agency: str
    call_sign: str
    personnel_name: str
    employee_number: str
    vehicle_number: str
    apparatus_type: Optional[str] = None

class OffDutyRequest(BaseModel):
    call_sign: str

class HistoricalSearchRequest(BaseModel):
    query_type: str  # "incidents" or "shift_history"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    call_sign: Optional[str] = None
    incident_number: Optional[str] = None

class DispatchRequest(BaseModel):
    incident_id: int
    unit_call_sign: str

class NCICVehicleRequest(BaseModel):
    incident_id: int
    plate_number: str
    state: str

class NCICSubjectRequest(BaseModel):
    incident_id: int
    first_name: str
    last_name: str
    dob: str
    dl_number: str
    dl_state: str
    race: str
    sex: str
    height: str
    weight: str

class UnitStatusRequest(BaseModel):
    incident_id: int
    unit_call_sign: str
    new_status: str  # "En Route", "On Scene", "Clear"

class AddCommentRequest(BaseModel):
    incident_id: int
    comment: str

class UpdateUnitRequest(BaseModel):
    call_sign: str
    agency: str
    vehicle_number: str
    apparatus_type: Optional[str] = None
    status: str

class FieldIncidentRequest(BaseModel):
    incident_type: str
    priority_level: int
    location: str
    common_place: Optional[str] = None
    description: str
    initiating_unit: str
    additional_notes: Optional[str] = None

class NewIncidentRequest(BaseModel):
    incident_type: str
    priority_level: int
    location: str
    common_place: Optional[str] = None
    description: str
    caller_name: str
    caller_phone: str

class TraineeRequest(BaseModel):
    first_name: str
    last_name: str
    badge_id: str

class EvaluationSessionRequest(BaseModel):
    trainee_id: int
    scenario_name: str

class TTSRequest(BaseModel):
    text: str
    source: str = "radio"  # "phone" or "radio"
    unit_call_sign: Optional[str] = None  # For unit-specific voice selection

class VoiceTranscribeRequest(BaseModel):
    audio_data: str  # Base64 encoded audio
    session_id: Optional[int] = None
    source: str  # "phone" or "radio"
    caller_persona: Optional[str] = None  # "panicked", "calm", "non_cooperative"
    initial_statement: Optional[str] = None  # Initial statement from scenario
    radio_call: Optional[dict] = None  # For radio unit conversations
    unit_call_sign: Optional[str] = None  # Unit call sign for consistent voice selection

class EvaluationMetricRequest(BaseModel):
    session_id: int
    metric_type: str
    expected_value: str
    actual_value: str

# API Routes
@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

@app.post("/api/on-duty")
async def on_duty(request: OnDutyRequest):
    """Move personnel onto a call sign and add to active unit roster"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if call sign already exists
        cursor.execute("SELECT id FROM units WHERE call_sign = ?", (request.call_sign,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing unit
            cursor.execute("""
                UPDATE units 
                SET agency = ?, vehicle_number = ?, apparatus_type = ?, status = 'Available', updated_at = ?
                WHERE call_sign = ?
            """, (request.agency, request.vehicle_number, request.apparatus_type, datetime.now(), request.call_sign))
            unit_id = existing['id']
            # Remove existing personnel for this unit
            cursor.execute("DELETE FROM unit_personnel WHERE unit_id = ?", (unit_id,))
        else:
            # Create new unit
            cursor.execute("""
                INSERT INTO units (call_sign, agency, vehicle_number, apparatus_type, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'Available', ?, ?)
            """, (request.call_sign, request.agency, request.vehicle_number, request.apparatus_type, datetime.now(), datetime.now()))
            unit_id = cursor.lastrowid
        
        # Add personnel to unit (single person as per new requirement)
        cursor.execute("""
            INSERT INTO unit_personnel (unit_id, employee_number, assigned_at)
            VALUES (?, ?, ?)
        """, (unit_id, request.employee_number, datetime.now()))
        
        conn.commit()
        return {"status": "success", "message": f"Unit {request.call_sign} is now on duty", "unit_id": unit_id}
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/off-duty")
async def off_duty(request: OffDutyRequest):
    """Move shift metrics to history and purge from active roster"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get unit info before removing
        cursor.execute("SELECT * FROM units WHERE call_sign = ?", (request.call_sign,))
        unit = cursor.fetchone()
        
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Get personnel associated with unit
        cursor.execute("SELECT employee_number FROM unit_personnel WHERE unit_id = ?", (unit['id'],))
        personnel = [row['employee_number'] for row in cursor.fetchall()]
        
        # Create shift history record
        cursor.execute("""
            INSERT INTO shift_history (call_sign, agency, vehicle_number, apparatus_type, personnel_list, status, shift_start, shift_end)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (request.call_sign, unit['agency'], unit['vehicle_number'], unit['apparatus_type'],
              json.dumps(personnel), unit['status'], unit['created_at'], datetime.now()))
        
        # Remove personnel associations
        cursor.execute("DELETE FROM unit_personnel WHERE unit_id = ?", (unit['id'],))
        
        # Remove unit from active roster
        cursor.execute("DELETE FROM units WHERE call_sign = ?", (request.call_sign,))
        
        conn.commit()
        return {"status": "success", "message": f"Unit {request.call_sign} is now off duty"}
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/historical-search")
async def historical_search(request: HistoricalSearchRequest):
    """Search cleared incidents and shift history logs"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if request.query_type == "incidents":
            query = "SELECT * FROM incidents WHERE status = 'Cleared'"
            params = []
            
            if request.start_date:
                query += " AND created_at >= ?"
                params.append(request.start_date)
            if request.end_date:
                query += " AND created_at <= ?"
                params.append(request.end_date)
            if request.incident_number:
                query += " AND incident_number = ?"
                params.append(request.incident_number)
            
            query += " ORDER BY created_at DESC"
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            
        elif request.query_type == "shift_history":
            query = "SELECT * FROM shift_history WHERE 1=1"
            params = []
            
            if request.call_sign:
                query += " AND call_sign = ?"
                params.append(request.call_sign)
            if request.start_date:
                query += " AND shift_start >= ?"
                params.append(request.start_date)
            if request.end_date:
                query += " AND shift_end <= ?"
                params.append(request.end_date)
            
            query += " ORDER BY shift_start DESC"
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
        
        else:
            raise HTTPException(status_code=400, detail="Invalid query type")
        
        return {"status": "success", "results": results}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/active-units")
async def get_active_units():
    """Get all active units with their status and current incident assignment"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT u.id, u.call_sign, u.agency, u.vehicle_number, u.apparatus_type, u.status, u.current_incident_id, u.created_at, u.updated_at,
                   GROUP_CONCAT(up.employee_number) as personnel,
                   i.incident_number, i.incident_type, i.status as incident_status
            FROM units u
            LEFT JOIN unit_personnel up ON u.id = up.unit_id
            LEFT JOIN incidents i ON u.current_incident_id = i.id
            GROUP BY u.id
            ORDER BY u.call_sign
        """)
        units = []
        for row in cursor.fetchall():
            unit = {
                'id': row['id'],
                'call_sign': row['call_sign'],
                'agency': row['agency'],
                'vehicle_number': row['vehicle_number'],
                'apparatus_type': row['apparatus_type'],
                'status': row['status'],
                'current_incident_id': row['current_incident_id'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'personnel': row['personnel'].split(',') if row['personnel'] else [],
                'incident_number': row['incident_number'],
                'incident_type': row['incident_type'],
                'incident_status': row['incident_status']
            }
            units.append(unit)
        
        return {"status": "success", "units": units}
    
    finally:
        conn.close()

@app.get("/api/run-cards")
async def get_run_cards():
    """Get all run cards for incident type selection"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT short_code, incident_type, required_units FROM run_cards ORDER BY incident_type")
        run_cards = [dict(row) for row in cursor.fetchall()]
        
        return {"status": "success", "run_cards": run_cards}
    
    finally:
        conn.close()

@app.get("/api/active-incidents")
async def get_active_incidents():
    """Get all active incidents, sorted by priority and time"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT * FROM incidents 
            WHERE status != 'Cleared'
            ORDER BY 
                CASE 
                    WHEN status = 'Pending' THEN 0
                    ELSE 1
                END,
                priority_level DESC,
                created_at ASC
        """)
        incidents = [dict(row) for row in cursor.fetchall()]
        
        return {"status": "success", "incidents": incidents}
    
    finally:
        conn.close()

@app.get("/api/incident/{incident_id}")
async def get_incident_details(incident_id: int):
    """Get detailed information for a specific incident"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get incident details
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        incident = cursor.fetchone()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Convert incident to dict to ensure all fields are present
        incident_dict = dict(incident)
        
        # Get audit trail
        cursor.execute("""
            SELECT * FROM incident_audit_trail 
            WHERE incident_id = ? 
            ORDER BY timestamp ASC
        """, (incident_id,))
        audit_trail = [dict(row) for row in cursor.fetchall()]
        
        # Get NCIC vehicle queries for this incident
        cursor.execute("""
            SELECT * FROM ncic_vehicle_queries 
            WHERE incident_id = ? 
            ORDER BY query_timestamp DESC
        """, (incident_id,))
        vehicle_queries = [dict(row) for row in cursor.fetchall()]
        
        # Get NCIC subject queries for this incident
        cursor.execute("""
            SELECT * FROM ncic_subject_queries 
            WHERE incident_id = ? 
            ORDER BY query_timestamp DESC
        """, (incident_id,))
        subject_queries = [dict(row) for row in cursor.fetchall()]
        
        # Get run card for incident type (try exact match first, then partial match)
        cursor.execute("""
            SELECT * FROM run_cards 
            WHERE incident_type = ?
        """, (incident_dict['incident_type'],))
        run_card = cursor.fetchone()
        
        # If no exact match, try to find a partial match
        if not run_card:
            cursor.execute("""
                SELECT * FROM run_cards 
                WHERE incident_type LIKE ?
                LIMIT 1
            """, (f"%{incident_dict['incident_type']}%",))
            run_card = cursor.fetchone()
        
        # Get assigned units with their current status
        cursor.execute("""
            SELECT u.call_sign, u.apparatus_type, u.status, u.agency
            FROM units u
            WHERE u.current_incident_id = ?
            ORDER BY u.call_sign
        """, (incident_id,))
        assigned_units = [dict(row) for row in cursor.fetchall()]
        
        return {
            "status": "success",
            "incident": incident_dict,
            "audit_trail": audit_trail,
            "vehicle_queries": vehicle_queries,
            "subject_queries": subject_queries,
            "run_card": dict(run_card) if run_card else None,
            "assigned_units": assigned_units
        }
    
    finally:
        conn.close()

@app.post("/api/dispatch")
async def dispatch_units(request: DispatchRequest):
    """Dispatch units to an incident and update statuses"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get incident details
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (request.incident_id,))
        incident = cursor.fetchone()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Get unit details
        cursor.execute("SELECT * FROM units WHERE call_sign = ?", (request.unit_call_sign,))
        unit = cursor.fetchone()
        
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Update incident status if it was Pending
        if incident['status'] == 'Pending':
            cursor.execute("""
                UPDATE incidents 
                SET status = 'Dispatched', updated_at = ?
                WHERE id = ?
            """, (datetime.now(), request.incident_id))
            
            # Add audit trail entry
            cursor.execute("""
                INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (request.incident_id, "Status Change", "Incident status changed from Pending to Dispatched", "DISP-001", datetime.now()))
        
        # Update unit status to Dispatched and set current incident
        cursor.execute("""
            UPDATE units 
            SET status = 'DS', current_incident_id = ?, updated_at = ?
            WHERE call_sign = ?
        """, (request.incident_id, datetime.now(), request.unit_call_sign))
        
        # Update dispatched units for incident
        current_units = incident['dispatched_units'] or ""
        if current_units:
            updated_units = f"{current_units}, {request.unit_call_sign}"
        else:
            updated_units = request.unit_call_sign
        
        cursor.execute("""
            UPDATE incidents 
            SET dispatched_units = ?, updated_at = ?
            WHERE id = ?
        """, (updated_units, datetime.now(), request.incident_id))
        
        # Add audit trail entry for dispatch
        cursor.execute("""
            INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (request.incident_id, "Unit Dispatched", f"Unit {request.unit_call_sign} dispatched to incident", "DISP-001", datetime.now()))
        
        conn.commit()
        return {
            "status": "success", 
            "message": f"Unit {request.unit_call_sign} dispatched to incident {request.incident_id}",
            "incident_status": "Dispatched" if incident['status'] == 'Pending' else incident['status']
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/ncic-vehicle-query")
async def ncic_vehicle_query(request: NCICVehicleRequest):
    """Run NCIC vehicle query and save results"""
    import time
    import random
    
    # Simulate network delay
    time.sleep(2)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Generate mock NCIC data
        registration_statuses = ["Valid", "Suspended", "Expired"]
        years = ["2018", "2019", "2020", "2021", "2022", "2023", "2024"]
        makes = ["Ford", "Chevrolet", "Toyota", "Honda", "Nissan", "Dodge", "Jeep"]
        models = ["F-150", "Silverado", "Camry", "Civic", "Altima", "Ram", "Wrangler"]
        stolen_statuses = ["Clear", "STOLEN - NCIC HIT"]
        
        mock_data = {
            "registration_status": random.choice(registration_statuses),
            "year": random.choice(years),
            "make": random.choice(makes),
            "model": random.choice(models),
            "vin": f"1HG{random.randint(100000, 999999)}",
            "stolen_status": random.choice(stolen_statuses)
        }
        
        # Save query results to database
        cursor.execute("""
            INSERT INTO ncic_vehicle_queries 
            (incident_id, plate_number, state, registration_status, year, make, model, vin, stolen_status, query_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (request.incident_id, request.plate_number, request.state, 
              mock_data["registration_status"], mock_data["year"], mock_data["make"], 
              mock_data["model"], mock_data["vin"], mock_data["stolen_status"], datetime.now()))
        
        # Add audit trail entry
        cursor.execute("""
            INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (request.incident_id, "NCIC Vehicle Query", 
              f"NCIC Vehicle Query Transmitted - Plate: {request.plate_number} {request.state}", 
              "DISP-001", datetime.now()))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": "NCIC vehicle query completed",
            "data": mock_data
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/ncic-subject-query")
async def ncic_subject_query(request: NCICSubjectRequest):
    """Run NCIC subject query and save results"""
    import time
    import random
    
    # Simulate network delay
    time.sleep(2)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Generate mock NCIC data
        license_statuses = ["Valid", "Suspended", "Expired", "Revoked"]
        warrant_options = ["No Active Warrants", "ACTIVE WARRANT FOR ARREST - CAUTION", "WARRANT - FTA", "WARRANT - PROBATION VIOLATION"]
        
        mock_data = {
            "license_status": random.choice(license_statuses),
            "warrants": random.choice(warrant_options)
        }
        
        # Save query results to database
        cursor.execute("""
            INSERT INTO ncic_subject_queries 
            (incident_id, first_name, last_name, dob, dl_number, dl_state, race, sex, height, weight, license_status, warrants, query_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (request.incident_id, request.first_name, request.last_name, request.dob, 
              request.dl_number, request.dl_state, request.race, request.sex, request.height, request.weight,
              mock_data["license_status"], mock_data["warrants"], datetime.now()))
        
        # Add audit trail entry
        cursor.execute("""
            INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (request.incident_id, "NCIC Person Query", 
              f"NCIC Person Query Transmitted - {request.first_name} {request.last_name}", 
              "DISP-001", datetime.now()))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": "NCIC subject query completed",
            "data": mock_data
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/unit-status")
async def update_unit_status(request: UnitStatusRequest):
    """Update unit status and log to incident audit trail"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get incident details
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (request.incident_id,))
        incident = cursor.fetchone()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Get unit details
        cursor.execute("SELECT * FROM units WHERE call_sign = ?", (request.unit_call_sign,))
        unit = cursor.fetchone()
        
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Check if this is the last unit (for Clear status)
        is_last_unit = False
        if request.new_status == "Clear":
            dispatched_units = incident['dispatched_units'] or ""
            current_units = [u.strip() for u in dispatched_units.split(',') if u.strip()]
            is_last_unit = len(current_units) == 1 and request.unit_call_sign in current_units
        
        # Update unit status
        if request.new_status == "CL":  # Cleared
            new_unit_status = "AV"  # Available
            clear_incident = True
        else:
            new_unit_status = request.new_status
            clear_incident = False
        
        cursor.execute("""
            UPDATE units 
            SET status = ?, current_incident_id = ?, updated_at = ?
            WHERE call_sign = ?
        """, (new_unit_status, None if clear_incident else request.incident_id, datetime.now(), request.unit_call_sign))
        
        # Update incident's dispatched units
        if request.new_status == "CL":
            dispatched_units = incident['dispatched_units'] or ""
            current_units = [u.strip() for u in dispatched_units.split(',') if u.strip()]
            if request.unit_call_sign in current_units:
                current_units.remove(request.unit_call_sign)
            updated_units = ', '.join(current_units) if current_units else None
            
            cursor.execute("""
                UPDATE incidents 
                SET dispatched_units = ?, updated_at = ?
                WHERE id = ?
            """, (updated_units, datetime.now(), request.incident_id))
        
        # Add audit trail entry
        cursor.execute("""
            INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (request.incident_id, "Unit Status Change", 
              f"Unit {request.unit_call_sign} status changed to {request.new_status}", 
              "DISP-001", datetime.now()))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": f"Unit {request.unit_call_sign} status updated to {request.new_status}",
            "is_last_unit": is_last_unit,
            "unit_status": new_unit_status
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/add-comment")
async def add_comment(request: AddCommentRequest):
    """Add comment to incident audit trail"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Add audit trail entry for comment
        cursor.execute("""
            INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (request.incident_id, "Comment", request.comment, "DISP-001", datetime.now()))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": "Comment added to incident"
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/update-unit")
async def update_unit(request: UpdateUnitRequest):
    """Update unit details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if unit exists
        cursor.execute("SELECT * FROM units WHERE call_sign = ?", (request.call_sign,))
        unit = cursor.fetchone()
        
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Update unit details
        cursor.execute("""
            UPDATE units 
            SET agency = ?, vehicle_number = ?, apparatus_type = ?, status = ?, updated_at = ?
            WHERE call_sign = ?
        """, (request.agency, request.vehicle_number, request.apparatus_type, request.status, datetime.now(), request.call_sign))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": f"Unit {request.call_sign} updated successfully"
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

class ClearIncidentRequest(BaseModel):
    incident_id: int
    disposition_code: str

@app.post("/api/clear-incident")
async def clear_incident(request: ClearIncidentRequest):
    """Clear incident with disposition code"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get incident details
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (request.incident_id,))
        incident = cursor.fetchone()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Update incident status
        cursor.execute("""
            UPDATE incidents 
            SET status = 'Cleared', disposition_code = ?, updated_at = ?
            WHERE id = ?
        """, (request.disposition_code, datetime.now(), request.incident_id))
        
        # Return all assigned units to available status
        cursor.execute("""
            UPDATE units 
            SET status = 'AV', current_incident_id = NULL, updated_at = ?
            WHERE current_incident_id = ?
        """, (datetime.now(), request.incident_id))
        units_released = cursor.rowcount
        
        if units_released:
            cursor.execute("""
                INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (request.incident_id, "Units Released", 
                  f"{units_released} unit(s) returned to available", 
                  "DISP-001", datetime.now()))
        
        # Add audit trail entry
        cursor.execute("""
            INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (request.incident_id, "Incident Cleared", 
              f"Incident cleared with disposition: {request.disposition_code}", 
              "DISP-001", datetime.now()))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": f"Incident cleared with disposition: {request.disposition_code}"
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/field-incident")
async def create_field_incident(request: FieldIncidentRequest):
    """Create a field-initiated incident (e.g., traffic stop called in by unit)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Generate incident number
        year = datetime.now().year
        cursor.execute("SELECT COUNT(*) as count FROM incidents WHERE incident_number LIKE ?", (f"INC-{year}-%",))
        result = cursor.fetchone()
        count = result['count'] + 1
        incident_number = f"INC-{year}-{count:03d}"
        
        # Create incident
        cursor.execute("""
            INSERT INTO incidents (incident_number, status, priority_level, incident_type, location, common_place, description, caller_name, caller_phone, created_at, updated_at, dispatched_units)
            VALUES (?, 'Active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (incident_number, request.priority_level, request.incident_type, request.location, request.common_place,
              request.description, request.initiating_unit, 'Field Initiated', datetime.now(), datetime.now(), request.initiating_unit))
        
        incident_id = cursor.lastrowid
        
        # Add audit trail entry
        cursor.execute("""
            INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (incident_id, "Incident Created", 
              f"Field-initiated incident created by unit {request.initiating_unit} (On Scene): {request.description}", 
              request.initiating_unit, datetime.now()))
        
        # Update initiating unit status to On Scene (AR) and link to incident
        cursor.execute("""
            UPDATE units 
            SET status = 'AR', current_incident_id = ?, updated_at = ?
            WHERE call_sign = ?
        """, (incident_id, datetime.now(), request.initiating_unit))
        
        # Add additional notes to audit trail if provided
        if request.additional_notes:
            cursor.execute("""
                INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (incident_id, "Additional Notes", request.additional_notes, request.initiating_unit, datetime.now()))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": f"Field-initiated incident {incident_number} created successfully",
            "incident_id": incident_id,
            "incident_number": incident_number
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/new-incident")
async def new_incident(request: NewIncidentRequest):
    """Create a new incident"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Generate incident number
        incident_number = f"INC-2026-{datetime.now().strftime('%m%d%H%M')}"
        
        # Create new incident
        cursor.execute("""
            INSERT INTO incidents (incident_number, status, priority_level, incident_type, location, common_place, description, caller_name, caller_phone, created_at, updated_at)
            VALUES (?, 'Pending', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (incident_number, request.priority_level, request.incident_type, request.location, request.common_place,
              request.description, request.caller_name, request.caller_phone, datetime.now(), datetime.now()))
        
        incident_id = cursor.lastrowid
        
        # Add audit trail entry
        cursor.execute("""
            INSERT INTO incident_audit_trail (incident_id, action, details, user_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (incident_id, "Incident Created", "911 call received and logged", "DISP-001", datetime.now()))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": f"Incident {incident_number} created",
            "incident_id": incident_id,
            "incident_number": incident_number
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# ==================== EVALUATION MANAGEMENT ENDPOINTS ====================

@app.post("/api/trainee")
async def add_trainee(request: TraineeRequest):
    """Add a new trainee profile"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO trainees (first_name, last_name, badge_id)
            VALUES (?, ?, ?)
        """, (request.first_name, request.last_name, request.badge_id))
        
        trainee_id = cursor.lastrowid
        conn.commit()
        
        return {
            "status": "success",
            "message": "Trainee profile created",
            "trainee_id": trainee_id
        }
    
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Badge ID already exists")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/trainees")
async def get_trainees():
    """Get all trainee profiles"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM trainees WHERE is_active = 1")
        trainees = [dict(row) for row in cursor.fetchall()]
        
        return {"status": "success", "trainees": trainees}
    
    finally:
        conn.close()

@app.get("/api/scenarios")
async def get_scenarios():
    """Get available training scenarios"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT DISTINCT scenario_name FROM scenario_timelines")
        scenarios = [row[0] for row in cursor.fetchall()]
        
        return {"status": "success", "scenarios": scenarios}
    
    finally:
        conn.close()

@app.post("/api/evaluation/start")
async def start_evaluation(request: EvaluationSessionRequest):
    """Start a new evaluation session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create evaluation session
        cursor.execute("""
            INSERT INTO evaluation_sessions (trainee_id, scenario_name, start_time, status)
            VALUES (?, ?, ?, 'active')
        """, (request.trainee_id, request.scenario_name, datetime.now()))
        
        session_id = cursor.lastrowid
        
        # Log session start
        cursor.execute("""
            INSERT INTO session_audit_trail (session_id, event_type, event_details)
            VALUES (?, 'session_start', ?)
        """, (session_id, f"Evaluation started for scenario: {request.scenario_name}"))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": "Evaluation session started",
            "session_id": session_id
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/evaluation/end")
async def end_evaluation(request: dict):
    """End an evaluation session and calculate scores"""
    session_id = request.get('session_id')
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Update session end time
        cursor.execute("""
            UPDATE evaluation_sessions 
            SET end_time = ?, status = 'completed'
            WHERE id = ?
        """, (datetime.now(), session_id))
        
        # Calculate score (simplified - would use actual metrics)
        cursor.execute("""
            SELECT COUNT(*) as total, SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM evaluation_metrics
            WHERE session_id = ?
        """, (session_id,))
        
        result = cursor.fetchone()
        total = result['total'] if result else 0
        correct = result['correct'] if result else 0
        score = (correct / total * 100) if total > 0 else 0
        
        cursor.execute("""
            UPDATE evaluation_sessions 
            SET total_score = ?
            WHERE id = ?
        """, (score, session_id))
        
        # Log session end
        cursor.execute("""
            INSERT INTO session_audit_trail (session_id, event_type, event_details)
            VALUES (?, 'session_end', ?)
        """, (session_id, f"Evaluation ended. Score: {score:.1f}%"))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": "Evaluation session ended",
            "score": score
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# ==================== VOICE PIPELINE ENDPOINTS ====================

@app.post("/api/voice/transcribe")
async def transcribe_voice(request: VoiceTranscribeRequest):
    """Transcribe audio using OpenAI Whisper API"""
    try:
        print(f"Received request, audio length: {len(request.audio_data) if request.audio_data else 0}, initial_statement: {request.initial_statement}")
        
        # If this is an initial statement request, skip transcription and generate TTS
        if request.initial_statement:
            print(f"Playing initial statement: {request.initial_statement}")
            
            # Generate TTS for initial statement
            try:
                tts_audio = generate_tts(request.initial_statement, request.source)
                print(f"Initial TTS generated: {len(tts_audio) if tts_audio else 0} characters")
                
                return {
                    "status": "success",
                    "transcription": "",
                    "llm_response": "",
                    "tts_audio": tts_audio,
                    "is_initial": True
                }
            except Exception as e:
                print(f"Initial TTS error: {e}")
                return {
                    "status": "error",
                    "message": f"Failed to generate initial statement TTS: {str(e)}"
                }
        
        # Validate audio data for normal transcription
        if not request.audio_data or len(request.audio_data) < 100:
            return {
                "status": "error",
                "message": "Audio data too short or empty"
            }
        
        # Decode base64 audio
        import base64
        try:
            audio_data = base64.b64decode(request.audio_data)
        except Exception as e:
            print(f"Base64 decode error: {e}")
            return {
                "status": "error",
                "message": f"Invalid audio data: {str(e)}"
            }
        
        print(f"Decoded audio data, size: {len(audio_data)} bytes")
        
        # Call Groq Whisper API for transcription
        from groq import Groq
        try:
            client = Groq(api_key=settings.groq_api_key)
        except Exception as e:
            print(f"Groq client init error: {e}")
            return {
                "status": "error",
                "message": f"Groq client initialization failed: {str(e)}"
            }
        
        # Save audio to temporary file for Groq
        import tempfile
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            print(f"Temp file created: {temp_file_path}")
            
            # Transcribe using Groq Whisper
            with open(temp_file_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                    response_format="text"
                )
            
            # Groq returns text directly when response_format="text"
            transcription_text = transcription
            print(f"Transcription result: {transcription_text}")
            
        except Exception as e:
            print(f"Groq Whisper API error: {e}")
            return {
                "status": "error",
                "message": f"Groq transcription failed: {str(e)}"
            }
        finally:
            # Clean up temp file
            if temp_file_path:
                try:
                    import os
                    os.unlink(temp_file_path)
                except:
                    pass
        
        # Get CAD state for LLM context
        try:
            cad_state = await get_cad_state()
        except Exception as e:
            print(f"CAD state error: {e}")
            cad_state = {"active_incidents": 0, "dispatched_units": [], "timestamp": datetime.now().isoformat()}
        
        # Process through LLM
        llm_response = ""
        tts_audio = ""
        acknowledged = False
        try:
            if request.source == 'radio' and request.radio_call:
                llm_response, acknowledged = process_radio_response(transcription_text, request.radio_call)
                print(f"Radio unit response: {llm_response}, acknowledged: {acknowledged}")
            else:
                persona = get_persona_guidelines(request.source, request.caller_persona)
                llm_response = process_with_llm(transcription_text, persona, cad_state)
                print(f"LLM response: {llm_response}")
        except Exception as e:
            print(f"LLM error: {e}")
            llm_response = f"Error processing your request: {str(e)}"
        
        # Generate TTS audio
        try:
            tts_audio = generate_tts(llm_response, request.source)
            print(f"TTS audio generated: {len(tts_audio) if tts_audio else 0} characters")
        except Exception as e:
            print(f"TTS error: {e}")
            tts_audio = ""
        
        return {
            "status": "success",
            "transcription": transcription_text,
            "llm_response": llm_response,
            "tts_audio": tts_audio,
            "acknowledged": acknowledged
        }
    
    except Exception as e:
        print(f"Transcription error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e)
        }

async def get_cad_state():
    """Get current CAD state for LLM context"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get active incidents count
        cursor.execute("SELECT COUNT(*) FROM incidents WHERE status != 'Cleared'")
        incident_count = cursor.fetchone()[0]
        
        # Get dispatched units
        cursor.execute("SELECT call_sign FROM units WHERE status = 'DS'")
        dispatched_units = [row[0] for row in cursor.fetchall()]
        
        # Get phone lines on hold
        cursor.execute("SELECT COUNT(*) FROM units WHERE status = 'held'")
        # This would need phone line tracking in database
        
        return {
            "active_incidents": incident_count,
            "dispatched_units": dispatched_units,
            "timestamp": datetime.now().isoformat()
        }
    
    finally:
        conn.close()

def get_persona_guidelines(source, caller_persona=None):
    """Get persona guidelines based on source and caller type"""
    if source == "phone":
        # This is now the CALLER's persona
        if caller_persona == 'panicked':
            return {
                "role": "Emergency Caller",
                "tone": "panicked, urgent, emotional",
                "guidelines": "Speak quickly, may be incoherent, desperate for help, volunteer basic information like 'I need help' or 'Send police/fire' but wait for dispatcher to ask details"
            }
        elif caller_persona == 'calm':
            return {
                "role": "Emergency Caller",
                "tone": "calm, cooperative, professional",
                "guidelines": "Speak clearly, provide basic request like 'I need the fire department at [address]', wait for dispatcher to ask follow-up questions"
            }
        elif caller_persona == 'non_cooperative':
            return {
                "role": "Non-Emergency Caller",
                "tone": "frustrated, belligerent, impatient",
                "guidelines": "Sound annoyed, make basic demands like 'I need an officer' or 'Send someone', be reluctant to provide details, show frustration"
            }
        else:
            return {
                "role": "Caller",
                "tone": "neutral",
                "guidelines": "Provide basic request and wait for dispatcher to ask questions"
            }
    else:
        # Radio dispatch (not used for caller interactions)
        return {
            "role": "Radio Dispatcher",
            "tone": "concise, clear, professional",
            "guidelines": "Use standard 10-codes, keep transmissions brief, acknowledge all calls"
        }

def process_with_llm(text, persona, cad_state):
    """Process transcription through LLM with persona and context"""
    prompt = f"""
    You are a {persona['role']}. Maintain a {persona['tone']} tone.
    Guidelines: {persona['guidelines']}

    The 911 dispatcher just said: "{text}"

    Respond appropriately as the caller. Keep your response brief and realistic.
    - If you're panicked: Speak urgently, may repeat yourself, show fear
    - If you're calm: Answer clearly and concisely
    - If you're non-cooperative: Show frustration, give minimal information
    - DO NOT volunteer extra information unless specifically asked
    - Only provide what the dispatcher asks for
    """

    # Use OpenAI if available, otherwise fall back to Groq
    if settings.openai_api_key:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=100,
            temperature=0.8
        )
    else:
        # Fallback to Groq
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=100,
            temperature=0.8
        )

    return response.choices[0].message.content

def process_radio_response(dispatcher_text, radio_call):
    """Process a dispatcher radio transmission and generate the unit's response"""
    readout_name = radio_call.get('readout_name', 'Unit')
    call_sign = radio_call.get('call_sign', '')
    unit_message = radio_call.get('message', '')
    call_type = radio_call.get('type', 'enroute')
    stage = radio_call.get('stage', '')
    address = radio_call.get('incident_address', 'the incident')
    common_place = radio_call.get('incident_common_place', '')
    location = common_place if common_place else address

    # Determine if the dispatcher acknowledged the correct unit
    lower = (dispatcher_text or '').lower()

    # Check multiple variations of the unit identifier
    # 1. Exact call sign match (A12)
    # 2. Exact readout name match (Adam Twenty One)
    # 3. Partial letter+number match (Adam 12 should match Adam Twenty One)
    # 4. Fire/EMS units: "Engine 1", "Ladder 2", "Medic 3" should match
    # 5. EMS units without space: "ALS1", "BLS2", "QRV3" should match
    # 6. Lenient: If dispatcher says the unit type + "go ahead", accept it
    # 7. Super lenient: If dispatcher just says "go ahead" with an active call, accept it
    # 8. 10-codes: "10-4 [call sign]" or "[call sign] 10-4" should be accepted
    right = False
    if call_sign and call_sign.lower() in lower:
        right = True
    elif readout_name and readout_name.lower() in lower:
        right = True
    elif call_sign:
        # For police units like A12, dispatcher might say "Adam 12" or "A 12"
        import re
        # Match pattern like "Adam 12" or "A 12"
        match = re.search(r'([a-z]+)\s*(\d+)', lower)
        if match:
            letter_part = match.group(1)
            number = match.group(2)
            # Try to match phonetic word to single letter
            phonetic_map = {
                'adam': 'a', 'baker': 'b', 'charlie': 'c', 'david': 'd',
                'edward': 'e', 'frank': 'f', 'george': 'g', 'henry': 'h',
                'ida': 'i', 'john': 'j', 'king': 'k', 'lincoln': 'l',
                'mary': 'm', 'nora': 'n', 'ocean': 'o', 'paul': 'p',
                'queen': 'q', 'robert': 'r', 'sam': 's', 'tom': 't',
                'union': 'u', 'victor': 'v', 'william': 'w', 'x-ray': 'x',
                'young': 'y', 'zebra': 'z'
            }
            # Convert phonetic to single letter if applicable
            letter = phonetic_map.get(letter_part, letter_part)
            # If it's already a single letter, use it
            if len(letter_part) == 1:
                letter = letter_part
            # Check if this matches the call sign pattern
            if call_sign.lower().startswith(letter) and number in call_sign:
                right = True
    else:
        # For fire/EMS units, try to match words like "engine", "ladder", "medic" + number
        import re
        # Match "engine 1", "ladder 2", "medic 3"
        match = re.search(r'(engine|ladder|rescue|battalion|medic|als|bls|qrv)\s*(\d+)', lower)
        if match:
            unit_type = match.group(1)
            number = match.group(2)
            # Map unit type to call sign prefix
            type_map = {
                'engine': 'eng', 'ladder': 'lad', 'rescue': 'res',
                'battalion': 'bc', 'medic': 'med', 'als': 'med',
                'bls': 'bls', 'qrv': 'qrv'
            }
            prefix = type_map.get(unit_type, unit_type)
            # Check if call sign matches prefix-number pattern
            if call_sign.lower().startswith(prefix) and number in call_sign:
                right = True
        else:
            # Match EMS units without space: "ALS1", "BLS2", "QRV3"
            match = re.search(r'(als|bls|qrv)(\d+)', lower)
            if match:
                unit_type = match.group(1)
                number = match.group(2)
                # Map unit type to call sign prefix
                type_map = {
                    'als': 'med', 'bls': 'bls', 'qrv': 'qrv'
                }
                prefix = type_map.get(unit_type, unit_type)
                # Check if call sign matches prefix-number pattern
                if call_sign.lower().startswith(prefix) and number in call_sign:
                    right = True
                    print(f"Matched unit without space: '{unit_type}{number}' to prefix '{prefix}'")
            # Lenient match: if dispatcher says the unit type and "go ahead", accept it
            # This handles cases where transcription misses the number
            if 'go ahead' in lower:
                unit_type_words = {
                    'engine': 'eng', 'ladder': 'lad', 'rescue': 'res',
                    'battalion': 'bc', 'medic': 'med', 'als': 'med',
                    'bls': 'bls', 'qrv': 'qrv'
                }
                for word, prefix in unit_type_words.items():
                    if word in lower and call_sign.lower().startswith(prefix):
                        right = True
                        print(f"Lenient match: '{word}' matched to prefix '{prefix}'")
                        break
                # Super lenient: if dispatcher just says "go ahead" with no unit identifier,
                # accept it as acknowledgment (context is the active radio call)
                if not right and 'go ahead' in lower:
                    right = True
                    print(f"Super lenient match: 'go ahead' accepted without unit identifier")
            # 10-code acknowledgment: "10-4 [call sign]" or "[call sign] 10-4"
            if '10-4' in lower or '10 4' in lower:
                # Extract potential call sign from text
                # Try to match any of the unit identifiers in the text
                potential_matches = [call_sign.lower(), readout_name.lower()]
                for match in potential_matches:
                    if match in lower:
                        right = True
                        print(f"10-4 acknowledgment matched: '{match}'")
                        break

    repeat = 'say again' in lower or 'repeat' in lower or 'come again' in lower or 'what was' in lower
    acknowledged = right and not repeat

    # Debug logging
    print(f"Radio response check - Dispatcher said: '{dispatcher_text}'")
    print(f"  Call sign: {call_sign}, Readout name: {readout_name}")
    print(f"  Lowercase: '{lower}'")
    print(f"  Right match: {right}, Repeat: {repeat}, Acknowledged: {acknowledged}")

    if stage == 'checkin':
        # Unit called in with "[call sign] to radio"; dispatcher should say "go ahead"
        if acknowledged:
            if call_type == 'enroute':
                return f"{readout_name}, en route to {location}", True
            else:
                return f"{readout_name}, on scene, {location}", True
        else:
            if repeat:
                return f"{readout_name} to radio", False
            else:
                return f"Dispatch, this is {readout_name}, {readout_name} to radio", False

    # Normal acknowledgement (arrival sizeup etc.)
    status = 'en route' if call_type == 'enroute' else 'on scene'
    prompt = f"""You are {readout_name}, a unit on the radio. Your original transmission was: \"{unit_message}\".
The dispatcher just said: \"{dispatcher_text}\".
# If they acknowledged you correctly and used your call sign, respond briefly with \"Copy, {readout_name}, {status}.\"
If they used the wrong call sign, correct them: \"Dispatch, this is {readout_name}, {unit_message}.\"
If they asked you to repeat, repeat the same message briefly.
Keep your response under 15 words and realistic for radio traffic. Do not explain anything."""

    # Use OpenAI if available, otherwise fall back to Groq
    if settings.openai_api_key:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Faster and cheaper than full GPT-4
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": dispatcher_text}
            ],
            max_tokens=60,
            temperature=0.5
        )
    else:
        # Fallback to Groq
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": dispatcher_text}
            ],
            max_tokens=60,
            temperature=0.5
        )

    return response.choices[0].message.content.strip(), acknowledged

def generate_tts(text, source, unit_call_sign=None):
    """Generate TTS audio using Groq"""
    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)

        # Select voice based on source and unit
        # For phone calls: use a more natural, conversational voice
        # For radio: use a consistent voice per unit for realism
        # Groq supported voices: autumn, diana, hannah, austin, daniel, troy
        if source == 'phone':
            voice = "hannah"  # Natural, conversational voice
        elif unit_call_sign:
            # Select a consistent voice for each unit based on hash of call sign
            voices = ["autumn", "diana", "hannah", "austin", "daniel", "troy"]
            # Use a simple hash to pick a voice
            voice_index = sum(ord(c) for c in unit_call_sign) % len(voices)
            voice = voices[voice_index]
        else:
            voice = "daniel"  # Default dispatcher voice

        # Generate audio using Groq TTS
        response = client.audio.speech.create(
            model="canopylabs/orpheus-v1-english",
            voice=voice,
            input=text,
            response_format="wav"
        )
        
        # Write to temp file then read back
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_file_path = temp_file.name
        
        response.write_to_file(temp_file_path)
        
        # Read the file and convert to base64
        with open(temp_file_path, "rb") as f:
            audio_bytes = f.read()
        
        # Clean up temp file
        import os
        os.unlink(temp_file_path)
        
        # Convert to base64
        import base64
        audio_base64 = base64.b64encode(audio_bytes).decode()
        
        print(f"Groq TTS generated: {len(audio_base64)} characters")
        return audio_base64
    
    except Exception as e:
        print(f"Groq TTS Error: {e}")
        import traceback
        traceback.print_exc()
        # Return empty string on error
        return ""

@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Generate TTS audio for radio or phone readout"""
    try:
        audio_base64 = await asyncio.to_thread(generate_tts, request.text, request.source, request.unit_call_sign)
        if audio_base64:
            return {"status": "success", "audio": audio_base64}
        else:
            return {"status": "error", "message": "TTS generation failed"}
    except Exception as e:
        print(f"TTS endpoint error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/scenario-timeline/{scenario_name}")
async def get_scenario_timeline(scenario_name: str):
    """Get timeline triggers for a specific scenario"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT trigger_time_seconds, event_type, event_data
            FROM scenario_timelines
            WHERE scenario_name = ?
            ORDER BY trigger_time_seconds
        """, (scenario_name,))
        
        triggers = [dict(row) for row in cursor.fetchall()]
        
        return {"status": "success", "triggers": triggers}
    
    finally:
        conn.close()

@app.post("/api/evaluation/metric")
async def log_evaluation_metric(request: EvaluationMetricRequest):
    """Log an evaluation metric"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Simple comparison for correctness
        is_correct = request.expected_value == request.actual_value
        
        cursor.execute("""
            INSERT INTO evaluation_metrics (session_id, metric_type, expected_value, actual_value, is_correct)
            VALUES (?, ?, ?, ?, ?)
        """, (request.session_id, request.metric_type, request.expected_value, request.actual_value, is_correct))
        
        conn.commit()
        
        return {"status": "success"}
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
