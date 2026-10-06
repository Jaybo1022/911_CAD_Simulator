import sqlite3
import os
from datetime import datetime

def add_scenario_data():
    """Add sample scenario timeline data for training evaluation"""
    
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, "cad_simulator.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Clear existing scenario timeline data to avoid duplicates
        cursor.execute("DELETE FROM scenario_timelines")
        
        # Sample scenarios with timeline triggers
        scenarios = [
            {
                'name': 'Active Shooter',
                'triggers': [
                    (30, 'incoming_call', '{"type": "emergency", "caller": "555-1234", "location": "123 Main St - High School", "description": "Active shooter reported", "caller_persona": "panicked", "initial_statement": "Oh my god! There\'s a shooter! Send help!"}'),
                    (90, 'incoming_call', '{"type": "emergency", "caller": "555-5678", "location": "123 Main St - Gymnasium", "description": "Additional shots fired", "caller_persona": "panicked", "initial_statement": "More shots! In the gym!"}'),
                    (180, 'unit_request', '{"unit_type": "PD", "quantity": 4}'),
                    (300, 'update_status', '{"incident_id": 1, "status": "Active"}')
                ]
            },
            {
                'name': 'Structure Fire',
                'triggers': [
                    (45, 'incoming_call', '{"type": "emergency", "caller": "555-2345", "location": "456 Oak Ave - Apartment Complex", "description": "Fire reported, people trapped", "caller_persona": "calm", "initial_statement": "I need the fire department. There\'s a fire at 456 Oak Avenue."}'),
                    (120, 'incoming_call', '{"type": "emergency", "caller": "555-6789", "location": "456 Oak Ave - Unit 2B", "description": "Multiple units needed", "caller_persona": "calm", "initial_statement": "This is 2B. We need more units here, people are trapped."}'),
                    (200, 'unit_request', '{"unit_type": "ENG", "quantity": 3}'),
                    (250, 'unit_request', '{"unit_type": "LAD", "quantity": 1}')
                ]
            },
            {
                'name': 'Animal Disturbance',
                'triggers': [
                    (60, 'incoming_call', '{"type": "non-emergency", "caller": "555-3456", "location": "789 Elm St", "description": "Aggressive dog reported", "caller_persona": "non_cooperative", "initial_statement": "I need someone to come deal with this dog. It\'s been barking for hours."}'),
                    (150, 'update_location', '{"location": "789 Elm St - Backyard"}')
                ]
            }
        ]
        
        for scenario in scenarios:
            for trigger in scenario['triggers']:
                cursor.execute("""
                    INSERT INTO scenario_timelines (scenario_name, trigger_time_seconds, event_type, event_data)
                    VALUES (?, ?, ?, ?)
                """, (scenario['name'], trigger[0], trigger[1], trigger[2]))
        
        conn.commit()
        print("Scenario timeline data added successfully!")
        
    except Exception as e:
        print(f"Error adding scenario data: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_scenario_data()
