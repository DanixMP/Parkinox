"""
NYW - Flask API for YOLO plate detection
Uses the extracted PlateDetector module
"""
import logging
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np

from plate_detector import PlateDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global detector instance
detector = None

def init_detector():
    """Initialize plate detector"""
    global detector
    try:
        logger.info("Initializing plate detector...")
        detector = PlateDetector()
        logger.info("✓ Plate detector initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize detector: {e}", exc_info=True)
        return False

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'models_loaded': detector is not None
    })

@app.route('/detect', methods=['POST'])
def detect():
    """
    Detect license plate from uploaded image
    
    Request:
        - Method: POST
        - Content-Type: multipart/form-data
        - Body: image file
    
    Response:
        {
            "success": true/false,
            "plate": "۱۲ ب ۳۴۵ ۶۷",
            "confidence": 0.85,
            "num_characters": 8,
            "char_confidence": 0.75
        }
    """
    if detector is None:
        return jsonify({
            'success': False,
            'error': 'Detector not initialized'
        }), 500
    
    try:
        # Get image from request
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No image provided'
            }), 400
        
        file = request.files['image']
        img_bytes = file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return jsonify({
                'success': False,
                'error': 'Invalid image'
            }), 400
        
        logger.info(f"Processing image: {image.shape[1]}x{image.shape[0]}")
        
        # Detect plate
        plate_text, confidence, metadata = detector.detect(image)
        
        if plate_text:
            result = {
                'success': True,
                'plate': plate_text,
                'confidence': round(confidence, 3),
                'num_characters': len(plate_text.replace(' ', '')),
                'char_confidence': round(metadata.get('char_confidence', 0), 3) if metadata else 0,
                'bbox': metadata.get('bbox', []) if metadata else []
            }
            logger.info(f"✓ Detection successful: {result}")
            return jsonify(result)
        else:
            result = {
                'success': False,
                'message': 'No plate detected',
                'plate': None,
                'confidence': 0.0,
                'num_characters': 0
            }
            logger.info(f"No plate detected")
            return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error during detection: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/detect/file', methods=['POST'])
def detect_file():
    """
    Detect plate from file path (for testing)
    
    Request:
        {
            "path": "/path/to/image.jpg"
        }
    """
    if detector is None:
        return jsonify({
            'success': False,
            'error': 'Detector not initialized'
        }), 500
    
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({
                'success': False,
                'error': 'No path provided'
            }), 400
        
        image_path = Path(data['path'])
        if not image_path.exists():
            return jsonify({
                'success': False,
                'error': f'File not found: {image_path}'
            }), 400
        
        logger.info(f"Processing file: {image_path}")
        
        # Detect plate
        plate_text, confidence, metadata = detector.detect_from_file(str(image_path))
        
        if plate_text:
            result = {
                'success': True,
                'plate': plate_text,
                'confidence': round(confidence, 3),
                'num_characters': len(plate_text.replace(' ', '')),
                'char_confidence': round(metadata.get('char_confidence', 0), 3) if metadata else 0
            }
            logger.info(f"✓ Detection successful: {result}")
            return jsonify(result)
        else:
            return jsonify({
                'success': False,
                'message': 'No plate detected',
                'plate': None,
                'confidence': 0.0
            })
    
    except Exception as e:
        logger.error(f"Error during detection: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("NYW - YOLO Plate Detection API")
    logger.info("="*60)
    
    # Initialize detector
    if init_detector():
        logger.info("Starting Flask server on http://localhost:5000")
        app.run(host='0.0.0.0', port=5000, debug=True)
    else:
        logger.error("Failed to initialize. Exiting.")
        exit(1)
