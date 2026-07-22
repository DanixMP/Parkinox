import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:parkinox_op/core/constants.dart';
import 'package:parkinox_op/data/services/plate_detection_service.dart';
import 'package:parkinox_op/providers/continuous_detection_provider.dart';
import 'package:parkinox_op/providers/cross_camera_plate_guard.dart';
import 'package:parkinox_op/providers/operator_feedback_provider.dart';

PlateDetectionResult _result(String plate) => PlateDetectionResult(
      plate: plate,
      confidence: 0.9,
      charConfidence: 0.9,
      numCharacters: plate.replaceAll(' ', '').length,
      bbox: const [0, 0, 100, 100],
    );

void main() {
  group('ContinuousDetectionNotifier remote ingest', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
    });

    test('ingestRemoteDetection pulses isDetecting then clears', () {
      final notifier =
          container.read(entryContinuousDetectionProvider.notifier);
      var sawDetecting = false;
      container.listen(entryContinuousDetectionProvider, (prev, next) {
        if (next.isDetecting) sawDetecting = true;
      });

      notifier.ingestRemoteDetection(_result('12 ب 345 17'));

      expect(sawDetecting, isTrue);
      expect(
        container.read(entryContinuousDetectionProvider).isDetecting,
        isFalse,
      );
      expect(
        container.read(entryContinuousDetectionProvider).lastResult?.plate,
        '12 ب 345 17',
      );
    });

    test('allowIngest block does not add to queue and emits feedback', () {
      CrossCameraPlateGuard.instance.record('88 د 888 88', false);

      final notifier =
          container.read(entryContinuousDetectionProvider.notifier);
      notifier.ingestRemoteDetection(_result('88د88888'));

      final state = container.read(entryContinuousDetectionProvider);
      expect(state.lastResult, isNull);
      expect(state.detectionQueue, isEmpty);
      expect(
        container.read(operatorFeedbackProvider)?.message,
        crossCameraBlockedMessage(true),
      );
    });

    test('two different plates queue second behind first', () {
      final notifier =
          container.read(entryContinuousDetectionProvider.notifier);
      notifier.ingestRemoteDetection(_result('12 ب 345 17'));
      notifier.ingestRemoteDetection(_result('22 ج 456 18'));

      final state = container.read(entryContinuousDetectionProvider);
      expect(state.lastResult?.plate, '12 ب 345 17');
      expect(state.detectionQueue.length, 1);
      expect(state.detectionQueue.first.plate, '22 ج 456 18');
    });

    test('detectionQueue respects maxEventQueueSize', () {
      final notifier =
          container.read(entryContinuousDetectionProvider.notifier);
      notifier.ingestRemoteDetection(_result('11 الف 111 11'));

      for (var i = 0; i < AppConstants.maxEventQueueSize + 5; i++) {
        notifier.ingestRemoteDetection(
          _result('99 ب ${100 + i} ${200 + i}'),
        );
      }

      final state = container.read(entryContinuousDetectionProvider);
      expect(
        state.detectionQueue.length,
        lessThanOrEqualTo(AppConstants.maxEventQueueSize),
      );
    });

    test('OCR jitter on serial merges into active plate instead of queueing', () {
      final notifier =
          container.read(exitContinuousDetectionProvider.notifier);
      notifier.ingestRemoteDetection(_result('11 ج 216 17'));
      notifier.ingestRemoteDetection(_result('11 ج 217 17'));

      final state = container.read(exitContinuousDetectionProvider);
      expect(state.lastResult?.plate, '11 ج 217 17');
      expect(state.detectionQueue, isEmpty);
    });
  });

  group('crossCameraBlockedMessage', () {
    test('mentions two-minute cooldown for entry and exit', () {
      expect(crossCameraBlockedMessage(true), contains('۲ دقیقه'));
      expect(crossCameraBlockedMessage(false), contains('۲ دقیقه'));
    });
  });
}
