# EuroEventos Startup Script for Windows PowerShell
# This script starts both the Flask app and RabbitMQ worker

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  EuroEventos Application Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment is activated
if (-not $env:VIRTUAL_ENV) {
    Write-Host "[!] Virtual environment not detected. Activating..." -ForegroundColor Yellow
    if (Test-Path ".\venv\Scripts\Activate.ps1") {
        & .\venv\Scripts\Activate.ps1
    } else {
        Write-Host "[!] Virtual environment not found at .\venv\" -ForegroundColor Red
        Write-Host "    Please create it with: python -m venv venv" -ForegroundColor Red
        exit 1
    }
}

Write-Host "[✓] Virtual environment active" -ForegroundColor Green
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "[!] .env file not found!" -ForegroundColor Red
    Write-Host "    Creating default .env..." -ForegroundColor Yellow
    "RABBITMQ_URL=amqp://guest:guest@nuted-ia.dev:7770/" | Out-File -FilePath ".env" -Encoding utf8
    Write-Host "[✓] .env created" -ForegroundColor Green
} else {
    Write-Host "[✓] .env file found" -ForegroundColor Green
    
    # Check if RabbitMQ_URL is set
    $envContent = Get-Content .env -Raw
    if ($envContent -match "RABBITMQ_URL") {
        Write-Host "[✓] RabbitMQ URL configured" -ForegroundColor Green
    } else {
        Write-Host "[!] Adding RabbitMQ URL to .env..." -ForegroundColor Yellow
        Add-Content .env "`nRABBITMQ_URL=amqp://guest:guest@nuted-ia.dev:7770/"
        Write-Host "[✓] RabbitMQ URL added" -ForegroundColor Green
    }
}
Write-Host ""

# Test RabbitMQ connection
Write-Host "Testing RabbitMQ connection..." -ForegroundColor Cyan
try {
    $testConnection = python -c "
import pika
try:
    conn = pika.BlockingConnection(pika.URLParameters('amqp://guest:guest@nuted-ia.dev:7770/'))
    print('connected')
    conn.close()
except Exception as e:
    print(f'failed: {e}')
" 2>&1
    
    if ($testConnection -match "connected") {
        Write-Host "[✓] RabbitMQ connection successful!" -ForegroundColor Green
    } else {
        Write-Host "[!] RabbitMQ connection failed: $testConnection" -ForegroundColor Red
        Write-Host "    Make sure RabbitMQ is running on nuted-ia.dev:7770" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[!] Error testing RabbitMQ: $_" -ForegroundColor Red
}
Write-Host ""

# Start Flask app in new window
Write-Host "Starting Flask application..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; .\venv\Scripts\Activate.ps1; python run.py"
Write-Host "[✓] Flask app started in new window (port 5000)" -ForegroundColor Green
Write-Host ""

# Wait a moment for Flask to start
Start-Sleep -Seconds 2

# Start Worker in new window
Write-Host "Starting RabbitMQ worker..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; .\venv\Scripts\Activate.ps1; python worker.py"
Write-Host "[✓] Worker started in new window" -ForegroundColor Green
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Application Started Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access points:" -ForegroundColor Cyan
Write-Host "  • Flask App:     http://localhost:5000" -ForegroundColor White
Write-Host "  • RabbitMQ UI:   https://nuted-ia.dev/rabbitmq/" -ForegroundColor White
Write-Host ""
Write-Host "To stop the applications, close the terminal windows." -ForegroundColor Yellow
Write-Host ""
