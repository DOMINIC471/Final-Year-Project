# 🏥 ICU Heart Rate Monitoring System

This project implements a **real-time, scalable ICU monitoring system** using **Apache Kafka**, **InfluxDB**, **TimescaleDB**, **VictoriaMetrics**, and **Django**.  
It ensures **fault-tolerant data ingestion** with **master-standby consumer failover**, **heartbeat detection**, **Prometheus metrics**, and **real-time visualization**.

---

## 📦 Project Structure

- `main.py` — Central controller: launches producer, consumers, and web dashboard
- `src/system/` — Kafka producer/consumer codes with heartbeat handling
- `hr_monitor/` — Django-based web dashboard and API
- `docker-compose.yml` — Defines Kafka, InfluxDB, TimescaleDB, VictoriaMetrics services
- `.env` — Environment configuration (tokens, settings)
- `data/` — Input heart rate CSV data
- `logs/` — Performance and DB write logs

---

## 🛠️ Setup Instructions (for macOS and Linux)

### 1. Clone the Repository
```bash
git clone https://gitlab.com/your-repo/icu-monitor.git
cd icu-monitor
```

### 2. Install Python Dependencies
(Using virtualenv)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
```
Edit `.env` and insert your InfluxDB authentication tokens:
- `INFLUXDB_MASTER_TOKEN`
- `INFLUXDB_STANDBY1_TOKEN`
- `INFLUXDB_STANDBY2_TOKEN`

### 4. Start Databases and Kafka
```bash
docker-compose up -d
```

### 5. Create Kafka Topics
```bash
docker exec -it kafka-1 bash
kafka-topics --create --topic heart_rate --bootstrap-server localhost:29092 --partitions 1 --replication-factor 1
kafka-topics --create --topic heartbeat --bootstrap-server localhost:29092 --partitions 1 --replication-factor 1
exit
```

## 🗄️ Database Setup

### 6. InfluxDB: Create Bucket
- Open [http://localhost:8086](http://localhost:8086)
- Organization: `FYP`
- Create Bucket: `sensor_data`
- Save generated tokens in `.env`
- Repeat for standby1 (`localhost:8087`) and standby2 (`localhost:8088`)

### 7. TimescaleDB: Create Table
```bash
psql -h localhost -p 5432 -U postgres -d sensor_data
# Password: mynewpassword
```
Then run:
```sql
CREATE TABLE heart_rate (
    bed_number VARCHAR(10),
    timestamp TIMESTAMPTZ,
    heart_rate INTEGER
);
SELECT create_hypertable('heart_rate', 'timestamp');
```
Exit with `\q`.

### 8. PostgreSQL (Baseline SQL): Create Table
```bash
psql -h localhost -p 5433 -U macbookpro -d baseline_sql
# Password: mybaselinepassword
```
Then run:
```sql
CREATE TABLE heart_rate (
    bed_number VARCHAR(10),
    timestamp TIMESTAMPTZ,
    heart_rate INTEGER
);
```
Exit with `\q`.

### 9. VictoriaMetrics: No Manual Setup Needed
VictoriaMetrics automatically accepts writes.

---

## 🚀 Launch the System

### 10. Start Everything
```bash
python3 main.py
```
This will:
- Launch Kafka producer
- Start master + standby consumers
- Launch Django dashboard

---

## 📽️ ICU Dashboard URLs
- Monitor: [http://localhost:8000/](http://localhost:8000/)
- Manager Panel: [http://localhost:8000/manager/](http://localhost:8000/manager/)

---

## 📊 Monitoring and Metrics
Each consumer exposes Prometheus metrics:
- Master: `localhost:8000/metrics`
- Standby1: `localhost:8010/metrics`
- Standby2: `localhost:8020/metrics`

Heartbeat files:
- `/tmp/heartbeat_master_alive`
- `/tmp/icu_promotion.lock`

---

## 📋 Quick Commands Summary
```bash
# Clone repo
git clone https://gitlab.com/your-repo/icu-monitor.git
cd icu-monitor

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set environment
cp .env.example .env

# Start services
docker-compose up -d

# Create Kafka topics
docker exec -it kafka-1 bash
kafka-topics --create --topic heart_rate --bootstrap-server localhost:29092 --partitions 1 --replication-factor 1
kafka-topics --create --topic heartbeat --bootstrap-server localhost:29092 --partitions 1 --replication-factor 1
exit

# Create TimescaleDB table
psql -h localhost -p 5432 -U postgres -d sensor_data
# CREATE TABLE heart_rate (bed_number VARCHAR(10), timestamp TIMESTAMPTZ, heart_rate INTEGER);
# SELECT create_hypertable('heart_rate', 'timestamp');

# Create Baseline SQL table
psql -h localhost -p 5433 -U macbookpro -d baseline_sql
# CREATE TABLE heart_rate (bed_number VARCHAR(10), timestamp TIMESTAMPTZ, heart_rate INTEGER);

# InfluxDB: Create bucket 'sensor_data' via UI (localhost:8086)

# Launch system
python3 main.py
```

---

# ✅ End of README.md
