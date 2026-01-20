#!/bin/bash

# Simple wrapper to run the expect test and save output

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="test_results"
OUTPUT_FILE="${OUTPUT_DIR}/test_run_${TIMESTAMP}.log"

mkdir -p "${OUTPUT_DIR}"

echo "==================================="
echo "Running Aletheia Test"
echo "Output: ${OUTPUT_FILE}"
echo "==================================="

./test_aletheia_interactive.exp 2>&1 | tee "${OUTPUT_FILE}"

echo ""
echo "==================================="
echo "Test completed!"
echo "Results saved to: ${OUTPUT_FILE}"
echo "==================================="
