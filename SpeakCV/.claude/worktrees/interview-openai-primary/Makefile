.PHONY: all dev frontend backend install install-frontend install-backend docker-up docker-down backup restore backup-list

# Directories
FRONTEND_DIR = src/frontend
BACKEND_DIR = src/backend

# Default target
all: dev

# Run both frontend and backend (Requires make -j2 for parallel execution)
dev:
	@echo "Starting frontend and backend..."
	@$(MAKE) -j2 frontend backend

# Run Frontend
frontend:
	@echo "Starting frontend server..."
	cd $(FRONTEND_DIR) && npm run dev

# Run Backend
backend:
	@echo "Starting backend server..."
	cd $(BACKEND_DIR) && python run_backend.py

# Install all dependencies
install: install-frontend install-backend

# Install Frontend dependencies
install-frontend:
	@echo "Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm install

# Install Backend dependencies
install-backend:
	@echo "Installing backend dependencies..."
	cd $(BACKEND_DIR) && pip install -r requirements.txt

# Start Docker Compose services
docker-up:
	@echo "Starting Docker containers..."
	docker-compose up -d

# Stop Docker Compose services
docker-down:
	@echo "Stopping Docker containers..."
	docker-compose down

# ===== Database Backup & Restore =====
BACKUP_DIR = backups
DB_NAME = speakcv
DB_USER = root
DB_PASS = 123
DB_HOST = localhost
DB_PORT = 3306
MYSQL_BIN = "C:/Program Files/MySQL/MySQL Server 8.0/bin"
TIMESTAMP = $(shell powershell -Command "Get-Date -Format 'yyyyMMdd_HHmmss'")

# Backup database (local MySQL)
backup:
	@echo "Backing up database '$(DB_NAME)'..."
	@if not exist $(BACKUP_DIR) mkdir $(BACKUP_DIR)
	$(MYSQL_BIN)/mysqldump.exe -u $(DB_USER) -p$(DB_PASS) -h $(DB_HOST) -P $(DB_PORT) --default-character-set=utf8mb4 --routines --triggers --single-transaction --result-file="$(BACKUP_DIR)/$(DB_NAME)_$(TIMESTAMP).sql" $(DB_NAME)
	@echo "Backup saved to $(BACKUP_DIR)/$(DB_NAME)_$(TIMESTAMP).sql"

# Restore database from a backup file (usage: make restore FILE=backups/speakcv_20260512.sql)
restore:
	@echo "Restoring database '$(DB_NAME)' from $(FILE)..."
	$(MYSQL_BIN)/mysql.exe -u $(DB_USER) -p$(DB_PASS) -h $(DB_HOST) -P $(DB_PORT) --default-character-set=utf8mb4 $(DB_NAME) < $(FILE)
	@echo "Database restored successfully from $(FILE)"

# Backup database (Docker MySQL)
backup-docker:
	@echo "Backing up database from Docker container..."
	@if not exist $(BACKUP_DIR) mkdir $(BACKUP_DIR)
	docker exec speakcv_db mysqldump -u root -p"thanhhoang@123" --default-character-set=utf8mb4 --routines --triggers --single-transaction $(DB_NAME) > $(BACKUP_DIR)/$(DB_NAME)_docker_$(TIMESTAMP).sql
	@echo "Docker backup saved to $(BACKUP_DIR)/$(DB_NAME)_docker_$(TIMESTAMP).sql"

# Restore database (Docker MySQL) (usage: make restore-docker FILE=backups/speakcv_docker_xxx.sql)
restore-docker:
	@echo "Restoring database to Docker container from $(FILE)..."
	docker exec -i speakcv_db mysql -u root -p"thanhhoang@123" --default-character-set=utf8mb4 $(DB_NAME) < $(FILE)
	@echo "Docker database restored successfully from $(FILE)"

# List all backups
backup-list:
	@echo "Available backups:"
	@dir /B $(BACKUP_DIR)\*.sql 2>nul || echo "  No backups found."
