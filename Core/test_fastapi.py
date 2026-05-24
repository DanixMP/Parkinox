"""
Test script for FastAPI plate detection bridge
Tests all endpoints with sample images
"""
import requests
import json
from pathlib import Path
import time

# API Configuration
BASE_URL = "http://localhost:8000"
SAMPLES_DIR = Path(__file__).parent / "samples"


def print_section(title):
    """Print formatted section header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def test_root():
    """Test root endpoint"""
    print_section("Testing Root Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_health():
    """Test health check endpoint"""
    print_section("Testing Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if data.get('models_loaded'):
            print(f"✓ Models loaded on device: {data.get('device')}")
        else:
            print("❌ Models not loaded")
        
        return response.status_code == 200 and data.get('models_loaded')
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_models_info():
    """Test models info endpoint"""
    print_section("Testing Models Info")
    try:
        response = requests.get(f"{BASE_URL}/models/info")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_detect_upload(image_path: Path):
    """Test plate detection with file upload"""
    print_section(f"Testing Detection: {image_path.name}")
    
    if not image_path.exists():
        print(f"❌ Image not found: {image_path}")
        return False
    
    try:
        with open(image_path, 'rb') as f:
            files = {'image': (image_path.name, f, 'image/jpeg')}
            
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/detect", files=files)
            elapsed = time.time() - start_time
            
            print(f"Status: {response.status_code}")
            print(f"Processing time: {elapsed:.3f}s")
            
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if data.get('success'):
                print(f"\n✓ Plate detected: {data.get('plate')}")
                print(f"  Confidence: {data.get('confidence'):.3f}")
                print(f"  Char Confidence: {data.get('char_confidence'):.3f}")
                print(f"  Characters: {data.get('num_characters')}")
                if data.get('bbox'):
                    print(f"  Bounding Box: {data.get('bbox')}")
            else:
                print(f"\n⚠ No plate detected")
                print(f"  Message: {data.get('message')}")
            
            return response.status_code == 200
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_detect_file_path(image_path: Path):
    """Test plate detection with file path"""
    print_section(f"Testing File Path Detection: {image_path.name}")
    
    if not image_path.exists():
        print(f"❌ Image not found: {image_path}")
        return False
    
    try:
        payload = {"path": str(image_path.absolute())}
        
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/detect/file",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        elapsed = time.time() - start_time
        
        print(f"Status: {response.status_code}")
        print(f"Processing time: {elapsed:.3f}s")
        
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if data.get('success'):
            print(f"\n✓ Plate detected: {data.get('plate')}")
            print(f"  Confidence: {data.get('confidence'):.3f}")
        else:
            print(f"\n⚠ No plate detected")
        
        return response.status_code == 200
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_invalid_image():
    """Test with invalid image data"""
    print_section("Testing Invalid Image Handling")
    try:
        # Send text file as image
        files = {'image': ('test.txt', b'not an image', 'text/plain')}
        response = requests.post(f"{BASE_URL}/detect", files=files)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Should return 400 error
        return response.status_code == 400
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  PARKINOX FASTAPI TEST SUITE")
    print("="*60)
    print(f"API URL: {BASE_URL}")
    print(f"Samples Directory: {SAMPLES_DIR}")
    
    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/", timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: FastAPI server is not running!")
        print("Please start the server first:")
        print("  python fastapi_app.py")
        return
    
    results = []
    
    # Test basic endpoints
    results.append(("Root Endpoint", test_root()))
    results.append(("Health Check", test_health()))
    results.append(("Models Info", test_models_info()))
    
    # Test detection with sample images
    if SAMPLES_DIR.exists():
        sample_images = list(SAMPLES_DIR.glob("*.jpg")) + list(SAMPLES_DIR.glob("*.webp"))
        
        if sample_images:
            # Test upload method
            for img in sample_images[:3]:  # Test first 3 images
                results.append((f"Upload: {img.name}", test_detect_upload(img)))
            
            # Test file path method
            if sample_images:
                results.append((f"File Path: {sample_images[0].name}", 
                              test_detect_file_path(sample_images[0])))
        else:
            print("\n⚠ No sample images found in samples directory")
    else:
        print(f"\n⚠ Samples directory not found: {SAMPLES_DIR}")
    
    # Test error handling
    results.append(("Invalid Image", test_invalid_image()))
    
    # Print summary
    print_section("TEST SUMMARY")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
    
    print("\n" + "="*60)
    print("API Documentation available at:")
    print(f"  Swagger UI: {BASE_URL}/docs")
    print(f"  ReDoc: {BASE_URL}/redoc")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
