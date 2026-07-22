import 'package:flutter_test/flutter_test.dart';
import 'package:parkinox_sec_op/core/constants.dart';

void main() {
  test('security branding constants', () {
    expect(AppConstants.appSubtitlePersian, contains('امنیت'));
    expect(AppConstants.entryCameraId, 'entry_camera');
    expect(AppConstants.exitCameraId, 'exit_camera');
  });
}
