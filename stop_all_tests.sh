#!/bin/bash
echo "🛑 Stopping all test processes..."
pkill -f consumerMaster.py
pkill -f producer.py
pkill -f monitor_resources.sh
pkill -f bash
echo "✅ All test processes stopped."