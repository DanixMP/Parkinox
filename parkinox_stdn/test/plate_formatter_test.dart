import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_application_4/shared/utils/plate_formatter.dart';

void main() {
  group('PlateFormatter', () {
    test('formats backend format with Persian digits and dash', () {
      // Backend format: ۱۲ب۳۴۵-۶۷
      final result = PlateFormatter.formatPlate('۱۲ب۳۴۵-۶۷');
      expect(result, '12 ب 345 67');
    });

    test('formats backend format with English digits and dash', () {
      // Backend format: 12ب345-67
      final result = PlateFormatter.formatPlate('12ب345-67');
      expect(result, '12 ب 345 67');
    });

    test('formats without dash', () {
      // Format: 12ب34567
      final result = PlateFormatter.formatPlate('12ب34567');
      expect(result, '12 ب 345 67');
    });

    test('formats with Arabic digits', () {
      // Arabic-Indic digits: ١٢ب٣٤٥-٦٧
      final result = PlateFormatter.formatPlate('١٢ب٣٤٥-٦٧');
      expect(result, '12 ب 345 67');
    });

    test('handles already formatted plates', () {
      final result = PlateFormatter.formatPlate('12 ب 345 67');
      expect(result, '12 ب 345 67');
    });

    test('handles freezone plates', () {
      final result = PlateFormatter.formatPlate('AB-123-45');
      expect(result, 'AB - 123 - 45');
    });

    test('normalizes Persian digits to English', () {
      final result = PlateFormatter.normalizeDigits('۱۲۳۴۵۶۷۸۹۰');
      expect(result, '1234567890');
    });

    test('normalizes Arabic digits to English', () {
      final result = PlateFormatter.normalizeDigits('٠١٢٣٤٥٦٧٨٩');
      expect(result, '0123456789');
    });

    test('converts English to Persian digits', () {
      final result = PlateFormatter.toPersianDigits('1234567890');
      expect(result, '۱۲۳۴۵۶۷۸۹۰');
    });
  });
}
