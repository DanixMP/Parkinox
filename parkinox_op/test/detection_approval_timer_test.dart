import 'package:flutter_test/flutter_test.dart';

import 'package:parkinox_op/core/constants.dart';
import 'package:parkinox_op/data/models/plate_lookup_result.dart';
import 'package:parkinox_op/providers/cross_camera_plate_guard.dart';
import 'package:parkinox_op/providers/detection_approval_timer_provider.dart';

void main() {
  group('resolveApprovalCountdownSeconds', () {
    test('returns 5s for null lookup', () {
      expect(
        resolveApprovalCountdownSeconds(null),
        AppConstants.plateAutoApproveSeconds,
      );
    });

    test('returns 5s for lookup error', () {
      final lookup = PlateLookupResult.error('network error');
      expect(
        resolveApprovalCountdownSeconds(lookup),
        AppConstants.plateAutoApproveSeconds,
      );
    });

    test('returns 5s for unregistered plate', () {
      final lookup = PlateLookupResult.notRegistered('12ب34517');
      expect(
        resolveApprovalCountdownSeconds(lookup),
        AppConstants.plateAutoApproveSeconds,
      );
    });

    test('returns 5s for registered plate with balance', () {
      final lookup = PlateLookupResult(
        found: true,
        isRegistered: true,
        plateNumber: '12ب34517',
        walletBalance: 10000,
      );
      expect(
        resolveApprovalCountdownSeconds(lookup),
        AppConstants.plateAutoApproveSeconds,
      );
    });

    test('returns 5s for registered plate with zero balance', () {
      final lookup = PlateLookupResult(
        found: true,
        isRegistered: true,
        plateNumber: '12ب34517',
        walletBalance: 0,
      );
      expect(
        resolveApprovalCountdownSeconds(lookup),
        AppConstants.plateAutoApproveSeconds,
      );
    });
  });

  group('resolveExitCountdownSeconds', () {
    test('delegates to unified 5s approval timer', () {
      final lookup = PlateLookupResult.notRegistered('12ب34517');
      expect(
        resolveExitCountdownSeconds(lookup),
        resolveApprovalCountdownSeconds(lookup),
      );
    });
  });

  group('DetectionApprovalTimerNotifier multi-key', () {
    test('tracks independent timers per key', () {
      final notifier = DetectionApprovalTimerNotifier();
      addTearDown(notifier.dispose);

      notifier.markWaitingLookup(
        key: 'entry:12 ب 345 17',
        isEntry: true,
        plate: '12 ب 345 17',
      );
      notifier.markWaitingLookup(
        key: 'exit:22 ج 456 18',
        isEntry: false,
        plate: '22 ج 456 18',
      );

      expect(notifier.state.length, 2);
      expect(
        notifier.state['entry:12 ب 345 17']?.phase,
        ApprovalTimerPhase.waitingLookup,
      );
      expect(
        notifier.state['exit:22 ج 456 18']?.phase,
        ApprovalTimerPhase.waitingLookup,
      );
    });

    test('start decrements remaining for one key only', () async {
      final notifier = DetectionApprovalTimerNotifier();
      addTearDown(notifier.dispose);

      notifier.start(
        key: 'entry:A',
        plate: 'A',
        isEntry: true,
        seconds: 3,
      );
      notifier.start(
        key: 'exit:B',
        plate: 'B',
        isEntry: false,
        seconds: 5,
      );

      expect(notifier.state['entry:A']?.remaining, 3);
      expect(notifier.state['exit:B']?.remaining, 5);

      await Future<void>.delayed(const Duration(seconds: 1));

      expect(notifier.state['entry:A']?.remaining, 2);
      expect(notifier.state['exit:B']?.remaining, 4);
    });

    test('cancelKey removes only the targeted timer', () {
      final notifier = DetectionApprovalTimerNotifier();
      addTearDown(notifier.dispose);

      notifier.start(
        key: 'entry:A',
        plate: 'A',
        isEntry: true,
        seconds: 10,
      );
      notifier.start(
        key: 'exit:B',
        plate: 'B',
        isEntry: false,
        seconds: 10,
      );

      notifier.cancelKey('entry:A');

      expect(notifier.state.containsKey('entry:A'), isFalse);
      expect(notifier.state['exit:B']?.remaining, 10);
    });

    test('cancelAll clears every timer', () {
      final notifier = DetectionApprovalTimerNotifier();
      addTearDown(notifier.dispose);

      notifier.start(
        key: 'entry:A',
        plate: 'A',
        isEntry: true,
        seconds: 10,
      );
      notifier.start(
        key: 'exit:B',
        plate: 'B',
        isEntry: false,
        seconds: 10,
      );

      notifier.cancelAll();

      expect(notifier.state, isEmpty);
    });

    test('expiry callback fires with key, plate, and isEntry', () async {
      final notifier = DetectionApprovalTimerNotifier();
      addTearDown(notifier.dispose);

      String? expiredKey;
      String? expiredPlate;
      bool? expiredIsEntry;
      notifier.setOnExpired((key, plate, isEntry) {
        expiredKey = key;
        expiredPlate = plate;
        expiredIsEntry = isEntry;
      });

      notifier.start(
        key: 'exit:X',
        plate: 'X',
        isEntry: false,
        seconds: 1,
      );

      await Future<void>.delayed(const Duration(milliseconds: 1100));

      expect(expiredKey, 'exit:X');
      expect(expiredPlate, 'X');
      expect(expiredIsEntry, isFalse);
      expect(notifier.state.containsKey('exit:X'), isFalse);
    });

    test('start sets running phase with full 5s remaining immediately', () {
      final notifier = DetectionApprovalTimerNotifier();
      addTearDown(notifier.dispose);

      notifier.start(
        key: 'entry:12B345',
        plate: '12 ب 345 17',
        isEntry: true,
        seconds: AppConstants.plateAutoApproveSeconds,
      );

      final state = notifier.state['entry:12B345'];
      expect(state?.phase, ApprovalTimerPhase.running);
      expect(state?.remaining, AppConstants.plateAutoApproveSeconds);
      expect(state?.max, AppConstants.plateAutoApproveSeconds);
    });

    test('cancelIfMatches drops OCR-similar orphan timers', () {
      final notifier = DetectionApprovalTimerNotifier();
      addTearDown(notifier.dispose);

      notifier.start(
        key: 'exit:11J216',
        plate: '11 ج 216 17',
        isEntry: false,
        seconds: 5,
      );

      notifier.cancelIfMatches(isEntry: false, plate: '11 ج 217 17');

      expect(notifier.state.containsKey('exit:11J216'), isFalse);
    });
  });

  group('CrossCameraPlateGuard platesMatch', () {
    final guard = CrossCameraPlateGuard.instance;

    test('matches spaced and compact national plates', () {
      expect(guard.platesMatch('12 ب 345 17', '12ب34517'), isTrue);
    });

    test('tolerates one serial digit OCR flip', () {
      expect(guard.platesSimilar('11 ج 216 17', '11 ج 217 17'), isTrue);
    });

    test('does not match different plates', () {
      expect(guard.platesMatch('12 ب 345 17', '22 ج 456 18'), isFalse);
    });

    test('expiry pending lookup finds format variant', () {
      const timerPlate = '12ب34517';
      const pendingPlate = '12 ب 345 17';
      expect(guard.platesMatch(pendingPlate, timerPlate), isTrue);
    });
  });
}
