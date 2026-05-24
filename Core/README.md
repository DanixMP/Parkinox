# NYW - YOLO Plate Detection System

Standalone license plate detection system using YOLOv5 models. Extracted from the legacy operator_panel code for independent testing and deployment.

## Features

- **Two-stage detection**: Plate region detection + character recognition
- **Persian plate support**: National plates (۲۲ب۳۳۳۴۴) and free zone plates
- **REST API**: Simple Flask API for integration
- **Web UI**: Black and white interface for testing
- **Self-contained**: All models included in `models/` directory

## Directory Structure

```
NYW/
├── plate_detector.py      # Core detection module (extracted from legacy)
├── app.py                  # Flask API server
├── test_detector.py        # Test script
├── test_client.html        # Web UI for testing
├── requirements.txt        # Python dependencies
├── models/                 # YOLO model files
│   ├── plateYolo.pt       # Plate region detection model
│   └── CharsYolo.pt       # Character recognition model
├── debug/                  # Debug images (auto-created)
└── README.md
```

## Installation

Dependencies are already available in your base conda environment:
- Flask
- flask-cors
- opencv-python
- torch
- torchvision
- numpy
- Pillow
- ultralytics

## Quick Start

### 1. Test the detector module

```bash
python test_detector.py
```

### 2. Start the API server

```bash
python app.py
```

The server will start at: `http://localhost:5000`

### 3. Open the web UI

Open `test_client.html` in your browser:
```
file:///d:/Projects/A-Projects/Parkinox-v1/NYW/test_client.html
```

## API Endpoints

### GET /health
Check server status.

**Response:**
```json
{
    "status": "ok",
    "models_loaded": true
}
```

### POST /detect
Detect license plate from uploaded image.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: image file

**Response (Success):**
```json
{
    "success": true,
    "plate": "۷۵ ۶ ۵۴۵",
    "confidence": 0.85,
    "num_characters": 6,
    "char_confidence": 0.75,
    "bbox": [100, 50, 300, 100]
}
```

**Response (Failure):**
```json
{
    "success": false,
    "message": "No plate detected",
    "plate": null,
    "confidence": 0.0,
    "num_characters": 0
}
```

### POST /detect/file
Detect plate from file path (for testing).

**Request:**
```json
{
    "path": "/path/to/image.jpg"
}
```

## Using the Python Module

```python
from plate_detector import PlateDetector, detect_plate

# Method 1: Quick detection
plate, confidence = detect_plate("image.jpg")
print(f"Plate: {plate}, Confidence: {confidence:.2f}")

# Method 2: Full detector with metadata
detector = PlateDetector()
plate, conf, metadata = detector.detect("image.jpg")

if plate:
    print(f"Plate: {plate}")
    print(f"Confidence: {conf:.3f}")
    print(f"Character confidence: {metadata['char_confidence']:.3f}")
    print(f"Bounding box: {metadata['bbox']}")
```

## Detection Pipeline

1. **Plate Region Detection** (`plateYolo.pt`)
   - Detects license plate regions in the full image
   - Confidence threshold: 0.5

2. **Plate Crop & Resize**
   - Crops the detected region with padding
   - Resizes to 320x80 pixels (standard size for character model)

3. **Character Recognition** (`CharsYolo.pt`)
   - Detects individual characters in the cropped plate
   - Sorts characters left-to-right
   - Assembles the plate string

4. **Formatting**
   - National plates: `۲۲ ب ۳۳۳ ۴۴` (2 digits + letter + 3 digits + 2 digits)
   - Free zone plates: `۱۲۳۴۵ ۶۷` (5 digits + 2 digits)

## Models

Both models are trained YOLOv5 models:

- **plateYolo.pt**: Detects license plate regions
- **CharsYolo.pt**: Recognizes Persian digits and letters

Character classes:
- Persian digits: ۰-۹ (0-9)
- Persian letters: الف, ب, پ, ت, ث, ج, چ, ح, خ, د, ر, ز, س, ش, ع, ک, گ, ل, م, ن, و, ه, ی

## Debugging

Debug images are automatically saved to the `debug/` directory when running `test_detector.py` or `diagnose.py`.

## Notes

- Models are loaded from `NYW/models/` if available, otherwise from `operator_panel/models/`
- Detection works best with well-lit, front-facing plates
- Minimum image size: ~640px width recommended
- The module is standalone and doesn't require the operator_panel to be present (only the models)
