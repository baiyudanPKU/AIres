# 检查虚拟环境是否存在
if (Test-Path "venv") {
    Write-Host "Activating virtual environment..."
    .\venv\Scripts\Activate.ps1
} else {
    Write-Host "Virtual environment not found. Creating it..."
    python -m venv venv
    .\venv\Scripts\Activate.ps1
}

# 启动应用
Write-Host "Starting the application..."
try {
    python run.py
}
finally {
    Write-Host "Deactivating virtual environment..."
    deactivate
    Write-Host "Virtual environment deactivated."
}