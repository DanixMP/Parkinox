import 'package:flutter_test/flutter_test.dart';
import 'package:parkinox_op/core/utils/tehran_datetime.dart';
import 'package:parkinox_op/data/models/plate_lookup_result.dart';

void main() {
  group('PlateLookupResult.fromJson', () {
    test('parses active session entry fields', () {
      final dto = PlateLookupResult.fromJson({
        'found': true,
        'is_registered': true,
        'plate_number': '۱۲ب۳۴۵-۶۷',
        'user': {
          'id': 1,
          'full_name': 'Test User',
          'phone': '+989121111111',
        },
        'wallet_balance': 50000,
        'has_active_session': true,
        'active_session_id': 42,
        'active_session_entry_time': '2026-07-19T06:30:00+00:00',
        'duration_minutes': 120,
        'estimated_fee': 15000,
        'entry_camera_id': 'entry',
        'is_active': true,
        'is_primary': true,
      });

      expect(dto.hasActiveSession, isTrue);
      expect(dto.activeSessionId, 42);
      expect(dto.activeSessionEntryTime, isNotNull);
      expect(dto.durationMinutes, 120);
      expect(dto.estimatedFee, 15000);
      expect(dto.entryCameraId, 'entry');
    });

    test('defaults missing session fields', () {
      final dto = PlateLookupResult.fromJson({
        'found': true,
        'is_registered': false,
        'plate_number': '۱۲ب۳۴۵-۶۷',
        'user': null,
        'wallet_balance': null,
      });

      expect(dto.hasActiveSession, isFalse);
      expect(dto.activeSessionId, isNull);
      expect(dto.activeSessionEntryTime, isNull);
      expect(dto.durationMinutes, isNull);
      expect(dto.estimatedFee, isNull);
      expect(dto.entryCameraId, isNull);
    });
  });

  group('TehranDateTime', () {
    test('formats UTC ISO as Tehran Gregorian wall clock', () {
      // 06:30 UTC = 10:00 Tehran (+03:30)
      final dt = DateTime.parse('2026-07-19T06:30:00Z');
      expect(TehranDateTime.formatDate(dt), '2026-07-19');
      expect(TehranDateTime.formatTime(dt), '10:00:00');
      expect(TehranDateTime.formatFull(dt), '2026-07-19 10:00:00');
    });
  });
}
