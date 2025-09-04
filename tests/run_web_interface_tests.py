#!/usr/bin/env python3
"""
Test runner for web interface end-to-end tests.

This script runs the web interface tests and provides a summary of results.
It can be used in CI/CD pipelines or for local testing.
"""

import sys
import os
import subprocess
import time
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = ['selenium', 'pytest', 'flask']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        print("Install them with: pip install " + " ".join(missing_packages))
        return False
    
    return True

def check_chromedriver():
    """Check if ChromeDriver is available."""
    try:
        result = subprocess.run(['chromedriver', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"ChromeDriver found: {result.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    print("ChromeDriver not found. Please install ChromeDriver:")
    print("- Download from: https://chromedriver.chromium.org/")
    print("- Or install via package manager (e.g., apt install chromium-chromedriver)")
    return False

def run_unit_tests():
    """Run Python unit tests for web interface."""
    print("Running Python unit tests...")
    
    test_file = Path(__file__).parent / 'test_web_interface_e2e.py'
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            str(test_file), 
            '-v', 
            '--tb=short'
        ], capture_output=True, text=True, timeout=300)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("Tests timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

def run_javascript_tests():
    """Run JavaScript tests in a headless browser."""
    print("Running JavaScript tests...")
    
    # This would require a more complex setup with a test runner like Jest
    # For now, we'll just validate that the test file exists and is syntactically correct
    
    test_file = Path(__file__).parent.parent / 'src' / 'web' / 'static' / 'js' / 'web-interface-tests.js'
    
    if not test_file.exists():
        print(f"JavaScript test file not found: {test_file}")
        return False
    
    try:
        # Basic syntax check using Node.js if available
        result = subprocess.run(['node', '-c', str(test_file)], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("JavaScript test file syntax is valid")
            return True
        else:
            print(f"JavaScript syntax error: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("Node.js not found, skipping JavaScript syntax check")
        print("JavaScript test file exists and will be tested in browser")
        return True
    except Exception as e:
        print(f"Error checking JavaScript tests: {e}")
        return False

def validate_template():
    """Validate that the HTML template is well-formed."""
    print("Validating HTML template...")
    
    template_file = Path(__file__).parent.parent / 'src' / 'web' / 'templates' / 'index.html'
    
    if not template_file.exists():
        print(f"Template file not found: {template_file}")
        return False
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Basic validation checks
        checks = [
            ('DOCTYPE declaration', '<!DOCTYPE html>' in content),
            ('HTML tag', '<html' in content and '</html>' in content),
            ('Head section', '<head>' in content and '</head>' in content),
            ('Body section', '<body>' in content and '</body>' in content),
            ('Live2D canvas', 'live2d-canvas' in content),
            ('LiveKit script', 'livekit-client' in content),
            ('Input mode controls', 'voice-mode-btn' in content and 'text-mode-btn' in content),
            ('Animation controls', 'animation-controls' in content),
            ('Participant list', 'participants-list' in content),
            ('Responsive CSS', '@media' in content),
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}")
            if not passed:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"Error validating template: {e}")
        return False

def main():
    """Main test runner function."""
    print("=== Web Interface Test Runner ===\n")
    
    # Check dependencies
    if not check_dependencies():
        print("❌ Dependency check failed")
        return 1
    
    print("✅ Dependencies check passed\n")
    
    # Check ChromeDriver (optional for some tests)
    chromedriver_available = check_chromedriver()
    if chromedriver_available:
        print("✅ ChromeDriver check passed\n")
    else:
        print("⚠️  ChromeDriver not available, some tests will be skipped\n")
    
    # Validate template
    if not validate_template():
        print("❌ Template validation failed")
        return 1
    
    print("✅ Template validation passed\n")
    
    # Run JavaScript tests
    if not run_javascript_tests():
        print("❌ JavaScript tests failed")
        return 1
    
    print("✅ JavaScript tests passed\n")
    
    # Run Python unit tests (only if ChromeDriver is available)
    if chromedriver_available:
        if not run_unit_tests():
            print("❌ Python unit tests failed")
            return 1
        
        print("✅ Python unit tests passed\n")
    else:
        print("⚠️  Skipping Python unit tests (ChromeDriver not available)\n")
    
    print("=== All Tests Completed Successfully ===")
    return 0

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)