#!/bin/bash

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        return 0
    else
        return 1
    fi
}

# Kill existing processes if ports are in use
if check_port 8000; then
    echo "Port 8000 is in use. Killing process..."
    lsof -ti:8000 | xargs kill -9
fi

if check_port 3000; then
    echo "Port 3000 is in use. Killing process..."
    lsof -ti:3000 | xargs kill -9
fi

echo "Starting Backend on port 8000..."
nohup ./venv/bin/uvicorn app.api.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

echo "Starting Frontend on port 3000..."
cd frontend-vanilla
nohup python3 -m http.server 3000 > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "System is running!"
echo "------------------------------------------------"
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000/docs"
echo "------------------------------------------------"
echo "Logs are being written to backend.log and frontend.log"
echo "To stop the servers, run: kill $BACKEND_PID $FRONTEND_PID"
