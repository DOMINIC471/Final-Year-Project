from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import datetime
import random
import socket
import time
from django.utils.timezone import now
from pathlib import Path
from influxdb_client import InfluxDBClient

# InfluxDB Setup
bucket = "sensor_data"
org = "FYP"

token_master = "hIcGBu5hfmzTDjLIExH052SFKhifQ2SZ1yqx1_j90iUcHPcMzA5zHubYjETy-jw7gWFznUqbVBZC-5q7QW7TFQ=="
token_standby1 = "TIAmpb29Ah3NN5PtkW_99HNyKigrv73N0thBqeKO3FMSSZnQnckhxIvcewNiGfZFWynxjO6lekSgj3BVk1fSoQ=="
token_standby2 = "kC9YPXuLXTjmlENkznr1CjodzlWWMiWUgn_OfW0scsPuKrHAkwJwdSmaRdD_iFpk1rSkU_j3OHUPE6GAdtZfiA=="

url_master = "http://localhost:8086"
url_standby1 = "http://localhost:8087"
url_standby2 = "http://localhost:8088"

clients = [
    InfluxDBClient(url=url_master, token=token_master, org=org),
    InfluxDBClient(url=url_standby1, token=token_standby1, org=org),
    InfluxDBClient(url=url_standby2, token=token_standby2, org=org)
]

def is_port_open(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except Exception:
        return False

def fallback_query(query):
    for client in clients:
        try:
            return client.query_api().query(query)
        except Exception as e:
            print(f"Query failed for client {client.url}: {e}")
            continue
    raise Exception("All InfluxDB nodes failed")

def parse_records(results):
    data = []
    for table in results:
        for record in table.records:
            data.append({
                'timestamp': record.get_time().isoformat(),
                'value': record.get_value()
            })
    return data

@csrf_exempt
def HeartRateAPIView(request):
    bed_number = request.GET.get('bed')
    range_param = request.GET.get('range', '1h')

    if not bed_number:
        return JsonResponse({'error': 'Missing bed parameter'}, status=400)

    now = datetime.datetime.utcnow().isoformat() + 'Z'
    hours_map = {
        '1h': 1, '2h': 2, '6h': 6, '12h': 12, '24h': 24
    }
    hours = hours_map.get(range_param, 1)
    past = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).isoformat() + 'Z'

    query_hist = f'''
    from(bucket: "{bucket}")
      |> range(start: {past}, stop: {now})
      |> filter(fn: (r) => r["_measurement"] == "heart_rate")
      |> filter(fn: (r) => r["_field"] == "heart_rate")
      |> filter(fn: (r) => r["bed_number"] == "{bed_number}")
    '''

    query_real = f'''
    from(bucket: "{bucket}")
      |> range(start: -1m)
      |> filter(fn: (r) => r["_measurement"] == "heart_rate")
      |> filter(fn: (r) => r["_field"] == "heart_rate")
      |> filter(fn: (r) => r["bed_number"] == "{bed_number}")
    '''

    try:
        hist_data = parse_records(fallback_query(query_hist))
        real_data = parse_records(fallback_query(query_real))
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({
        'bed_number': bed_number,
        'real_time': real_data,
        'historical': hist_data
    })

def display_index(request):
    return render(request, 'display/index.html')

def get_heartbeat_status(file_path, max_age_seconds=10):
    try:
        if file_path.exists():
            last_mod_time = file_path.stat().st_mtime
            current_time = time.time()
            if (current_time - last_mod_time) <= max_age_seconds:
                return "active"
            else:
                return "down"
        else:
            return "down"
    except Exception:
        return "down"

def manager_status(request):
    timestamp = now().isoformat()

    # Detect consumer liveness via heartbeat files
    heartbeat_files = {
        "master": Path("/tmp/heartbeat_master_alive"),
        "standby1": Path("/tmp/heartbeat_standby1_alive"),
        "standby2": Path("/tmp/heartbeat_standby2_alive"),
    }

    # Detect who is the current active consumer
    promotion_lock = Path("/tmp/icu_promotion.lock")
    active_consumer = "master"
    if promotion_lock.exists():
        try:
            active_consumer = promotion_lock.read_text().strip()
        except Exception:
            active_consumer = "unknown"

    kafka = []
    for role in ["master", "standby1", "standby2"]:
        status = get_heartbeat_status(heartbeat_files[role])
        kafka.append({
            "name": f"consumer_{role}",
            "role": "master" if role == active_consumer else "standby",
            "heartbeat": timestamp if status == "active" else "no heartbeat",
            "status": status
        })

    influx = {
        "master": "OK" if is_port_open("localhost", 8086) else "DOWN",
        "standby1": "OK" if is_port_open("localhost", 8087) else "DOWN",
        "standby2": "OK" if is_port_open("localhost", 8088) else "DOWN",
    }

    containers = [
        {"name": "Baseline SQL", "status": "active" if is_port_open("localhost", 5433) else "error"},
        {"name": "Baseline Standby 1", "status": "active" if is_port_open("localhost", 5436) else "error"},
        {"name": "Baseline Standby 2", "status": "active" if is_port_open("localhost", 5437) else "error"},
        {"name": "TimescaleDB", "status": "active" if is_port_open("localhost", 5432) else "error"},
        {"name": "Timescale Standby 1", "status": "active" if is_port_open("localhost", 5434) else "error"},
        {"name": "Timescale Standby 2", "status": "active" if is_port_open("localhost", 5435) else "error"},
        {"name": "VictoriaMetrics", "status": "active" if is_port_open("localhost", 8428) else "error"},
        {"name": "Victoria Standby 1", "status": "active" if is_port_open("localhost", 8429) else "error"},
        {"name": "Victoria Standby 2", "status": "active" if is_port_open("localhost", 8430) else "error"},
        {"name": "Kafka", "status": "active" if is_port_open("localhost", 29092) else "error"},
        {"name": "Zookeeper", "status": "active" if is_port_open("localhost", 2181) else "error"},
    ]

    return JsonResponse({
        "influx": influx,
        "kafka": kafka,
        "containers": containers
    })

def manager_index(request):
    return render(request, 'display/manager.html')
