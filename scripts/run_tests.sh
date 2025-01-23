#!/bin/bash

# Exit on error
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print with color
print_color() {
    color=$1
    message=$2
    echo -e "${color}${message}${NC}"
}

# Function to run tests
run_tests() {
    test_type=$1
    test_command=$2
    
    print_color $YELLOW "\nRunning ${test_type} tests..."
    if $test_command; then
        print_color $GREEN "✓ ${test_type} tests passed"
    else
        print_color $RED "✗ ${test_type} tests failed"
        exit 1
    fi
}

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Start Docker services
print_color $YELLOW "Starting Docker services..."
docker-compose up -d

# Wait for services to be ready
print_color $YELLOW "Waiting for services to be ready..."
sleep 5

# Run different test suites
run_tests "Unit" "docker-compose exec -T tests pytest tests/test_client.py -v"
run_tests "Memory" "docker-compose exec -T tests pytest tests/test_memory.py -v"
run_tests "Integration" "docker-compose exec -T tests pytest tests/test_integration.py -v"
run_tests "Performance" "docker-compose exec -T tests pytest tests/test_performance.py -v"

# Run full test suite with coverage
print_color $YELLOW "\nRunning full test suite with coverage..."
if docker-compose exec -T tests pytest tests/ -v --cov=src --cov-report=html -n auto; then
    print_color $GREEN "✓ Full test suite passed"
else
    print_color $RED "✗ Full test suite failed"
    exit 1
fi

# Generate test report
print_color $YELLOW "\nGenerating test report..."
docker-compose exec -T tests pytest --benchmark-only --benchmark-autosave

# Clean up
print_color $YELLOW "\nCleaning up..."
docker-compose down

print_color $GREEN "\nAll tests completed successfully!"
print_color $YELLOW "Coverage report available in htmlcov/index.html"
print_color $YELLOW "Benchmark results available in .benchmarks/" 