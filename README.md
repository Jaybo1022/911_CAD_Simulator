# 911 CAD Simulator - Dispatcher Training System

A local web application for 911 dispatcher training simulation, built with Python FastAPI backend and a modern HTML/Tailwind CSS frontend.

## Features

### Frontend CAD Panel
- **Active Incident Log Grid**: Automatically locks "Pending" calls at the top, sorted by Priority Level, then by time elapsed
- **Unit Status Display**: Shows active units and their status (Available, Dispatched, En Route, On Scene)
- **Selected Incident Display**: 
  - Scrollable time-stamped Audit Trail
  - Run Card requirement area
  - Editable text box for recommended units with "Dispatch" button
  - Side menu for vehicle tools, subject tools, location call history, and hazard alerts

### Backend & Database
- **SQLite Database**: Local database for storing incidents, units, personnel, and historical data
- **On-Duty Workflow**: Accept Agency/Call Sign, employee numbers, and vehicle numbers
- **Off-Duty Workflow**: Moves shift metrics to history log and purges unit from active roster
- **Historical Data Search**: Query cleared incidents and shift history logs

### Configuration
- Secure loading of OpenAI API key from `.env` file using python-dotenv
- Configurable database path and settings

## Project Structure

```
911_CAD_Simulator/
├── backend/
│   └── main.py              # FastAPI application with API routes
├── frontend/
│   └── index.html           # Main CAD interface with Tailwind CSS
├── database/
│   ├── init_db.py           # Database initialization script
│   └── cad_simulator.db     # SQLite database (created on first run)
├── static/                  # Static files directory
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (OpenAI API key)
├── start.bat                # Windows startup script
├── start.sh                 # Linux/Mac startup script
└── README.md               # This file
```

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Quick Start

#### Windows:
1. Double-click `start.bat` or run it from command prompt
2. The application will automatically:
   - Create a virtual environment
   - Install dependencies
   - Initialize the database
   - Start the server

#### Linux/Mac:
1. Make the startup script executable: `chmod +x start.sh`
2. Run: `./start.sh`
3. The application will automatically set up and start

#### Manual Setup:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python database/init_db.py

# Start the server
python backend/main.py
```

The application will be available at: `http://127.0.0.1:8000`

## Database Schema

### Tables Created:
- **units**: Active units on duty with call signs, agency, vehicle numbers, and status
- **unit_personnel**: Personnel assigned to units
- **incidents**: Active and cleared incidents with full details
- **incident_audit_trail**: Timestamped log of all incident actions
- **shift_history**: Historical record of unit shifts
- **location_history**: Historical calls by location
- **hazard_alerts**: Known hazards for locations
- **run_cards**: Standard response requirements by incident type
- **vehicle_tools**: Equipment available by vehicle type
- **subject_tools**: Subject-related resources and protocols

### Sample Data Included:
- 8 sample run cards (Fire, Medical, Police, MVA scenarios)
- 12 vehicle tool entries across different vehicle types
- 8 subject tool protocols for common medical scenarios

## API Endpoints

### Incident Management
- `GET /` - Main application interface
- `GET /api/active-incidents` - Get all active incidents sorted by priority
- `GET /api/incident/{incident_id}` - Get detailed incident information and audit trail

### Unit Management
- `GET /api/active-units` - Get all active units with personnel
- `POST /api/on-duty` - Move personnel onto a call sign
  ```json
  {
    "agency": "Fire Department",
    "call_sign": "ENG-1",
    "employee_numbers": ["EMP-101", "EMP-102"],
    "vehicle_number": "V-1001"
  }
  ```
- `POST /api/off-duty` - Move unit to shift history
  ```json
  {
    "call_sign": "ENG-1"
  }
  ```

### Historical Search
- `POST /api/historical-search` - Search cleared incidents and shift history
  ```json
  {
    "query_type": "incidents",
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "incident_number": "INC-2026-001"
  }
  ```

## Frontend Features

### Incident Log Grid
- Color-coded priority levels (1=Red, 2=Yellow, 3=Blue, 4=Green)
- Pending calls have animated border to draw attention
- Shows time elapsed since incident creation
- Click to select incident for detailed view

### Unit Status Display
- Real-time status indicators (Available, Dispatched, En Route, On Scene)
- Shows assigned personnel for each unit
- Quick access to on-duty/off-duty functions

### Selected Incident Panel
- **Run Card Requirements**: Shows required units based on incident type
- **Dispatch Interface**: Enter unit call signs and dispatch with one click
- **Audit Trail**: Chronological log of all incident actions with timestamps
- **Tools Menu**: Quick access to:
  - Vehicle tools and equipment
  - Subject protocols and medical procedures
  - Location call history
  - Active hazard alerts

## Configuration

### Environment Variables (.env)
```
OPENAI_API_KEY=your_openai_api_key_here
```

The application safely loads the OpenAI API key using python-dotenv. The `.env` file is already present in your project directory.

## Usage Workflow

### Starting a Shift
1. Use the "On Duty" button in the Unit Status panel
2. Enter Agency, Call Sign, employee numbers, and vehicle number
3. Unit appears in active roster with "Available" status

### Handling a Call
1. New calls appear in the Active Incident Log at the top
2. Click on a pending call to select it
3. Review the Run Card requirements for the incident type
4. Enter recommended units in the dispatch field
5. Click "Dispatch" to assign units
6. Unit status updates automatically

### Clearing an Incident
1. Select the incident
2. Click "Clear" button
3. Enter disposition code and notes
4. Incident moves to historical database

### Ending a Shift
1. Use the "Off Duty" button in the Unit Status panel
2. Enter the call sign to go off duty
3. Shift metrics automatically saved to history
4. Unit removed from active roster

## Security Notes

- The OpenAI API key is loaded from the `.env` file and never exposed in the frontend
- All database operations use parameterized queries to prevent SQL injection
- The application runs locally on `127.0.0.1:8000` by default

## Troubleshooting

### Port Already in Use
If port 8000 is already in use, modify the port in `backend/main.py`:
```python
uvicorn.run(app, host="127.0.0.1", port=8001)  # Change to available port
```

### Database Lock Issues
If you encounter database lock issues, ensure only one instance of the application is running.

### Missing Dependencies
If you get import errors, make sure you've activated the virtual environment and installed requirements:
```bash
pip install -r requirements.txt
```

## Future Enhancements

Potential features for future development:
- Real-time incident simulation with AI-generated scenarios
- Voice input for dispatch commands
- Multi-user support for training scenarios
- Advanced reporting and analytics
- Integration with real CAD systems for comparison training
- Mobile-responsive design for tablet use

## Support

For issues or questions about the simulator, please refer to the inline code documentation or check the database schema in `database/init_db.py` for detailed table structures.

---

**Built for dispatcher training by a 911 professional, for 911 professionals.**
