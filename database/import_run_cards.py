import pandas as pd
import sqlite3
import os
import json
from datetime import datetime

def import_run_cards_from_excel():
    """Import run cards from Excel spreadsheet to SQLite database with detailed unit breakdown"""
    
    # Paths
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, "cad_simulator.db")
    excel_path = os.path.join(os.path.dirname(db_dir), "Incident_Run_Cards.xlsx")
    
    if not os.path.exists(excel_path):
        print(f"Excel file not found at: {excel_path}")
        return False
    
    try:
        # Read Excel file
        print(f"Reading Excel file: {excel_path}")
        df = pd.read_excel(excel_path)
        
        print(f"Found {len(df)} rows in Excel file")
        print("Columns:", df.columns.tolist())
        print("First few rows:")
        print(df.head())
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Clear existing run cards
        cursor.execute("DELETE FROM run_cards")
        print("Cleared existing run cards")
        
        # Import data with detailed unit breakdown
        imported_count = 0
        
        for index, row in df.iterrows():
            try:
                # Extract data from columns (assuming column names match description)
                short_code = str(row.iloc[0]).strip() if len(row) > 0 else ''
                incident_type = str(row.iloc[1]).strip() if len(row) > 1 else ''
                
                # Extract unit counts from columns 2-9 (PD, ENG, LAD, RES, ALS, BLS, QRV, Specialty)
                # Columns 2-8 are unit counts, column 9 is specialty
                unit_breakdown = {}
                unit_columns = ['PD', 'ENG', 'LAD', 'RES', 'ALS', 'BLS', 'QRV']
                
                for i, unit_type in enumerate(unit_columns, start=2):
                    if i < len(row):
                        count = row.iloc[i]
                        if count and str(count).strip() not in ['-', '', '0']:
                            unit_breakdown[unit_type] = str(count).strip()
                
                # Get specialty units (column 9)
                specialty = str(row.iloc[9]).strip() if len(row) > 9 else ''
                if specialty and specialty != '-':
                    unit_breakdown['Specialty'] = specialty
                
                # Build required units string
                required_units_parts = []
                for unit_type, count in unit_breakdown.items():
                    if unit_type != 'Specialty':
                        required_units_parts.append(f"{unit_type}:{count}")
                
                required_units_str = ', '.join(required_units_parts) if required_units_parts else ''
                
                # Additional notes with specialty info
                additional_notes = f"Specialty: {specialty}" if specialty and specialty != '-' else "Standard response protocol"
                
                # Create JSON for detailed unit breakdown
                unit_breakdown_json = json.dumps(unit_breakdown)
                
                if short_code and incident_type:
                    cursor.execute("""
                        INSERT INTO run_cards (short_code, incident_type, required_units, priority_level, additional_notes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (short_code, incident_type, required_units_str, 3, additional_notes))
                    imported_count += 1
                    print(f"Imported: {short_code} - {incident_type} - Units: {unit_breakdown}")
                
            except Exception as e:
                print(f"Error importing row {index}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        print(f"Successfully imported {imported_count} run cards with detailed unit breakdown")
        return True
        
    except Exception as e:
        print(f"Error importing run cards: {e}")
        return False

if __name__ == "__main__":
    import_run_cards_from_excel()
