#!/bin/bash
set -e

echo "============================================"
echo "  Running Spark Processing Pipeline"
echo "============================================"

echo ""
echo "[1/3] Spark Clean Job..."
python processing/spark_clean.py
echo ""

echo "[2/3] Spark Enrich Job..."
python processing/spark_enrich.py
echo ""

echo "[3/3] Spark Transform Job..."
python processing/spark_transform.py
echo ""

echo "============================================"
echo "  All Spark jobs completed!"
echo "============================================"
