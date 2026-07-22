import 'package:flutter_test/flutter_test.dart';
import 'package:parkinox_op/data/models/detection_fail_dto.dart';

void main() {
  test('DetectionFailDto.fromJson parses review fields', () {
    final dto = DetectionFailDto.fromJson({
      'id': '11111111-1111-1111-1111-111111111111',
      'fail_type': 'ocr_invalid_format',
      'raw_ocr': '۱۲ب۳۴۵۶۷۸',
      'validation_error': 'bad',
      'plate_confidence': 0.91,
      'char_confidence': 0.5,
      'bbox': [1, 2, 3, 4],
      'camera_id': 'entry_camera',
      'direction': 'entry',
      'full_image_url': 'http://localhost/media/full.jpg',
      'scene_b_image_url': 'http://localhost/media/scene_b.jpg',
      'has_scene_b': true,
      'scene_b_source': 'rtsp_delayed',
      'crop_image_url': null,
      'local_data_path': '2026-07-18/abc',
      'review_status': 'pending',
      'not_a_plate': false,
      'label_ground_truth': null,
      'gate_event_id': null,
    });

    expect(dto.isPending, isTrue);
    expect(dto.failTypeLabel, contains('نوع A'));
    expect(dto.statusLabel, 'در انتظار');
    expect(dto.bbox, [1, 2, 3, 4]);
    expect(dto.plateConfidence, 0.91);
    expect(dto.hasSceneB, isTrue);
    expect(dto.sceneBSource, 'rtsp_delayed');
    expect(dto.sceneBImageUrl, 'http://localhost/media/scene_b.jpg');
  });

  test('DetectionFailDto.fromJson defaults missing scene B', () {
    final dto = DetectionFailDto.fromJson({
      'id': '22222222-2222-2222-2222-222222222222',
      'fail_type': 'ocr_empty',
      'raw_ocr': '',
      'validation_error': '',
      'camera_id': 'exit_camera',
      'direction': 'exit',
      'full_image_url': 'http://localhost/media/full.jpg',
      'local_data_path': '2026-07-18/xyz',
      'review_status': 'pending',
      'not_a_plate': false,
    });

    expect(dto.hasSceneB, isFalse);
    expect(dto.sceneBSource, '');
    expect(dto.sceneBImageUrl, isNull);
  });
}
