#!/usr/bin/env python3
"""
Test script for the /animate endpoint to verify it works correctly.
"""

import requests
import json
import sys

def test_animate_endpoint():
    """Test the /animate endpoint with valid data."""
    
    # Test data
    test_data = {
        "expression": "happy",
        "intensity": 0.7,
        "duration": 2.0,
        "priority": "normal",
        "sync_with_audio": False
    }
    
    url = "http://127.0.0.1:5000/animate"
    
    try:
        print(f"Testing animate endpoint: {url}")
        print(f"Sending data: {json.dumps(test_data, indent=2)}")
        
        response = requests.post(
            url,
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"Response data: {json.dumps(response_data, indent=2)}")
        except json.JSONDecodeError:
            print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Test passed!")
            return True
        else:
            print(f"❌ Test failed with status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - make sure the server is running on http://127.0.0.1:5000")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

def test_invalid_data():
    """Test the endpoint with invalid data to verify error handling."""
    
    test_cases = [
        # Missing required fields
        {"expression": "happy"},
        # Invalid types
        {"expression": "happy", "intensity": "invalid", "duration": 2.0, "priority": "normal"},
        # Invalid priority
        {"expression": "happy", "intensity": 0.7, "duration": 2.0, "priority": "invalid"},
        # Empty data
        {},
    ]
    
    url = "http://127.0.0.1:5000/animate"
    
    for i, test_data in enumerate(test_cases):
        try:
            print(f"\nTesting invalid case {i+1}: {json.dumps(test_data)}")
            
            response = requests.post(
                url,
                json=test_data,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 400:
                print("✅ Correctly returned 400 for invalid data")
                try:
                    error_data = response.json()
                    print(f"Error message: {error_data.get('error', 'No error message')}")
                except:
                    pass
            else:
                print(f"❌ Expected 400, got {response.status_code}")
                
        except Exception as e:
            print(f"❌ Test failed with error: {e}")

if __name__ == "__main__":
    print("Testing /animate endpoint...")
    print("=" * 50)
    
    # Test valid request
    success = test_animate_endpoint()
    
    # Test invalid requests
    test_invalid_data()
    
    print("\n" + "=" * 50)
    if success:
        print("Main test passed! The endpoint is working correctly.")
    else:
        print("Main test failed. Check the server logs for more details.")
        sys.exit(1)