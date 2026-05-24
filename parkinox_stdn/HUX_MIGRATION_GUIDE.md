# Hux UI Migration Guide

## Overview
This guide documents the migration from Moon Design to Hux UI library for the Parkinox application.

**Status**: ✅ Foundation Complete - Hux components ready to use!

## What Changed

### Dependencies
- **Removed**: `moon_design: ^1.1.0`
- **Added**: `hux: ^1.2.0`

### Theme System
- Removed `MoonTheme` and `MoonTokens` from theme extensions
- Hux components work seamlessly with Material 3 theming
- No wrapper widget needed - just import and use Hux components directly

### Files Modified
1. ✅ `pubspec.yaml` - Updated dependencies
2. ✅ `lib/app/theme.dart` - Removed Moon Design imports
3. ✅ `lib/main.dart` - Cleaned up imports

### New Files Created
1. ✅ `lib/shared/widgets/hux_components_showcase.dart` - Complete component showcase
2. ✅ `lib/features/home/widgets/parking_session_card_hux.dart` - Real-world parking card example
3. ✅ `lib/features/home/widgets/dashboard_stats_hux.dart` - Modern dashboard with Hux
4. ✅ `HUX_MIGRATION_GUIDE.md` - This guide

## How to Use Hux Components

Hux components are ready to use! Simply import and use them in your widgets:

```dart
import 'package:hux/hux.dart';
```

### Cards
```dart
HuxCard(
  elevation: 2,
  borderRadius: 16,
  child: Padding(
    padding: const EdgeInsets.all(16),
    child: Text('Card Content'),
  ),
)
```

### Text Fields
```dart
HuxTextField(
  label: 'Email',
  hint: 'Enter your email',
  prefixIcon: Icons.email,
  onChanged: (value) {},
)

// Password Field
HuxTextField(
  label: 'Password',
  obscureText: true,
  suffixIcon: Icons.visibility_off,
  onChanged: (value) {},
)
```

### Chips
```dart
HuxChip(
  label: 'Active',
  type: HuxChipType.filled,
  icon: Icons.check,
  onTap: () {},
)

// Deletable Chip
HuxChip(
  label: 'Tag',
  type: HuxChipType.outlined,
  onDelete: () {},
)
```

### Badges
```dart
HuxBadge(
  child: Icon(Icons.notifications),
  value: '5',
)

// Dot Badge
HuxBadge(
  child: Icon(Icons.mail),
  showDot: true,
)
```

### Switches & Checkboxes
```dart
HuxSwitch(
  value: isEnabled,
  onChanged: (value) => setState(() => isEnabled = value),
  label: 'Enable Feature',
)

HuxCheckbox(
  value: isChecked,
  onChanged: (value) => setState(() => isChecked = value),
  label: 'I agree',
)
```

### Progress Indicators
```dart
HuxProgressBar(
  value: 0.7, // 70%
  height: 8,
  color: Colors.blue,
)
```

### Avatars
```dart
// Text Avatar
HuxAvatar(
  radius: 24,
  child: Text('AB'),
)

// Icon Avatar
HuxAvatar(
  radius: 24,
  backgroundColor: Colors.blue,
  child: Icon(Icons.person, color: Colors.white),
)

// Image Avatar
HuxAvatar(
  radius: 24,
  imageUrl: 'https://example.com/avatar.jpg',
)
```

### Alerts
```dart
HuxAlert(
  type: HuxAlertType.success,
  title: 'Success',
  message: 'Operation completed successfully!',
)

HuxAlert(
  type: HuxAlertType.error,
  title: 'Error',
  message: 'Something went wrong.',
)

HuxAlert(
  type: HuxAlertType.warning,
  title: 'Warning',
  message: 'Please review your input.',
)

HuxAlert(
  type: HuxAlertType.info,
  title: 'Info',
  message: 'This is an informational message.',
)
```

### Dividers
```dart
HuxDivider()

// Custom Divider
HuxDivider(
  thickness: 2,
  color: Colors.grey,
)
```

## Migration Strategy

### Phase 1: Foundation (Completed ✓)
- [x] Update dependencies
- [x] Remove Moon Design imports
- [x] Add HuxApp wrapper
- [x] Create component showcase

### Phase 2: Component Migration (Recommended)
Replace existing Material widgets with Hux components for a modern look:

#### Buttons
- `ElevatedButton` → `HuxButton(type: HuxButtonType.primary)`
- `OutlinedButton` → `HuxButton(type: HuxButtonType.outlined)`
- `TextButton` → `HuxButton(type: HuxButtonType.text)`
- `FilledButton` → `HuxButton(type: HuxButtonType.primary)`

#### Cards
- `Card` → `HuxCard`

#### Text Fields
- `TextField` → `HuxTextField`
- `TextFormField` → `HuxTextField` (with validation)

#### Other Components
- `Chip` → `HuxChip`
- `Switch` → `HuxSwitch`
- `Checkbox` → `HuxCheckbox`
- `CircularProgressIndicator` → `HuxProgressBar` (for determinate progress)
- `Divider` → `HuxDivider`

### Phase 3: Custom Components
Create custom Hux-based components for:
- Parking session cards
- Vehicle plate displays
- Status indicators
- Dashboard widgets

## Example: Migrating a Screen

### Before (Material)
```dart
Card(
  child: Padding(
    padding: EdgeInsets.all(16),
    child: Column(
      children: [
        TextField(
          decoration: InputDecoration(labelText: 'Email'),
        ),
        SizedBox(height: 16),
        ElevatedButton(
          onPressed: () {},
          child: Text('Submit'),
        ),
      ],
    ),
  ),
)
```

### After (Hux)
```dart
HuxCard(
  child: Padding(
    padding: EdgeInsets.all(16),
    child: Column(
      children: [
        HuxTextField(
          label: 'Email',
          hint: 'Enter your email',
          prefixIcon: Icons.email,
          onChanged: (value) {},
        ),
        SizedBox(height: 16),
        HuxButton(
          text: 'Submit',
          onPressed: () {},
          type: HuxButtonType.primary,
        ),
      ],
    ),
  ),
)
```

## Testing the Migration

1. Run `flutter pub get` to install Hux
2. Check the showcase screen: `lib/shared/widgets/hux_components_showcase.dart`
3. Gradually migrate screens one at a time
4. Test both light and dark themes
5. Verify RTL support for Persian language

## Resources

- **Hux Documentation**: https://docs.thehuxdesign.com/
- **Hux GitHub**: https://github.com/lofidesigner/hux
- **Hux pub.dev**: https://pub.dev/packages/hux

## Notes

- Hux is fully compatible with Material 3
- All existing Material widgets continue to work
- Migration can be done incrementally
- Hux provides better consistency and modern design
- Components are highly customizable

## Next Steps

1. Review the component showcase
2. Identify high-priority screens for migration
3. Start with simple screens (settings, profile)
4. Move to complex screens (dashboard, sessions)
5. Create custom Hux-based components as needed

## Support

For issues or questions about Hux:
- Check the official documentation
- Review example code in the showcase file
- Consult the Hux GitHub repository
