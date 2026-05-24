# Parkinox FastAPI Bridge

Modern FastAPI bridge between Flutter UI and YOLOv5 plate detection system.

## Features

- ✅ **High Performance**: Async FastAPI for better concurrency
- ✅ **Auto Documentation**: Interactive API docs at `/docs` and `/redoc`
- ✅ **Type Safety**: Pydantic models for request/response validation
- ✅ **CORS Enabled**: Ready for Flutter web/mobile integration
- ✅ **Error Handling**: Comprehensive error responses with proper HTTP status codes
- ✅ **Health Checks**: Monitor system status and model loading

## Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Ensure YOLOv5 models are in place:**
   - `models/plateYolo.pt` - Plate detection model
   - `models/CharsYolo.pt` - Character recognition model

## Running the Server

### Development Mode (with auto-reload):
```bash
python fastapi_app.py
```

### Production Mode:
```bash
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
```

The server will start at: `http://localhost:8000`

## API Endpoints

### 1. Root
- **GET** `/`
- Returns API information

### 2. Health Check
- **GET** `/health`
- Check if models are loaded and system is ready
- Response:
```json
{
  "status": "ok",
  "models_loaded": true,
  "device": "cuda",
  "version": "1.0.0"
}
```

### 3. Detect Plate (Upload)
- **POST** `/detect`
- Upload image file for plate detection
- Content-Type: `multipart/form-data`
- Body: `image` (file)
- Response:
```json
{
  "success": true,
  "plate": "۱۲ ب ۳۴۵ ۶۷",
  "confidence": 0.85,
  "char_confidence": 0.75,
  "num_characters": 8,
  "bbox": [100, 200, 300, 250],
  "message": "Plate detected successfully"
}
```

### 4. Detect Plate (File Path)
- **POST** `/detect/file`
- Detect from server-side file path (for testing)
- Content-Type: `application/json`
- Body:
```json
{
  "path": "/path/to/image.jpg"
}
```

### 5. Models Info
- **GET** `/models/info`
- Get information about loaded models
- Response:
```json
{
  "plate_model": "models/plateYolo.pt",
  "char_model": "models/CharsYolo.pt",
  "device": "cuda",
  "conf_threshold": 0.5,
  "models_loaded": true
}
```

## Testing

Run the test suite:
```bash
python test_fastapi.py
```

This will test:
- ✅ All endpoints
- ✅ Image upload detection
- ✅ File path detection
- ✅ Error handling
- ✅ Performance metrics

## Interactive Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
  - Interactive API testing interface
  - Try out endpoints directly from browser
  
- **ReDoc**: http://localhost:8000/redoc
  - Clean, readable API documentation

## Flutter Integration

### Example: Detect Plate from Image

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:io';

Future<Map<String, dynamic>> detectPlate(File imageFile) async {
  final uri = Uri.parse('http://localhost:8000/detect');
  
  var request = http.MultipartRequest('POST', uri);
  request.files.add(
    await http.MultipartFile.fromPath('image', imageFile.path)
  );
  
  var response = await request.send();
  var responseData = await response.stream.bytesToString();
  
  return json.decode(responseData);
}

// Usage
void main() async {
  final result = await detectPlate(File('path/to/image.jpg'));
  
  if (result['success']) {
    print('Plate: ${result['plate']}');
    print('Confidence: ${result['confidence']}');
  } else {
    print('No plate detected');
  }
}
```

## Performance

Typical detection times:
- **GPU (CUDA)**: 50-150ms per image
- **CPU**: 200-500ms per image

## Error Handling

The API returns appropriate HTTP status codes:

- `200 OK`: Successful detection (even if no plate found)
- `400 Bad Request`: Invalid image or request format
- `404 Not Found`: File not found (file path endpoint)
- `500 Internal Server Error`: Server-side processing error
- `503 Service Unavailable`: Models not loaded

## Comparison: Flask vs FastAPI

| Feature | Flask (app.py) | FastAPI (fastapi_app.py) |
|---------|---------------|-------------------------|
| Performance | Good | Excellent (async) |
| Documentation | Manual | Auto-generated |
| Type Validation | Manual | Automatic (Pydantic) |
| Async Support | Limited | Native |
| API Testing UI | None | Built-in (/docs) |

## Configuration

Edit `fastapi_app.py` to customize:

```python
# CORS origins (for production)
allow_origins=["https://your-flutter-app.com"]

# Server port
port=8000

# Confidence threshold
detector = PlateDetector(conf_threshold=0.5)
```

## Troubleshooting

### Models not loading
- Check that model files exist in `models/` directory
- Verify PyTorch and CUDA installation (if using GPU)

### CORS errors from Flutter
- Ensure CORS middleware is properly configured
- Check that Flutter app URL is in `allow_origins`

### Slow detection
- Check if GPU is being used: see `/health` endpoint
- Consider reducing image size before upload
- Use GPU if available for 3-5x speedup

## Next Steps

1. ✅ Test the API with sample images
2. ✅ Integrate with Flutter UI
3. ⬜ Add authentication (JWT tokens)
4. ⬜ Add rate limiting
5. ⬜ Deploy to production server
6. ⬜ Add batch detection endpoint
7. ⬜ Add WebSocket support for real-time detection

## License

Part of Parkinox v3 project.
