#!/bin/bash

echo "Starting 911 CAD Simulator..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment."
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Failed to install dependencies."
    exit 1
fi

# Initialize database
echo "Initializing database..."
python3 database/init_db.py
if [ $? -ne 0 ]; then
    echo "Failed to initialize database."
    exit 1
fi

# Add sample data
echo "Adding sample data..."
python3 database/add_sample_data.py

# Import run cards from Excel
echo "Importing run cards from Excel..."
python3 database/import_run_cards.py

# Start the server
echo ""
echo "Starting FastAPI server..."
echo "The application will be available at: http://127.0.0.1:8000"
echo "Press Ctrl+C to stop the server."
echo ""
python3 backend/main.py
