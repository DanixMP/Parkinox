# 🎨 Hux UI Migration - Complete Guide

## ✅ Migration Status: COMPLETE

Moon Design has been successfully replaced with **Hux UI v1.2.0**!

## 📦 What Changed

### Dependencies
- ❌ Removed: `moon_design: ^1.1.0`
- ✅ Added: `hux: ^1.2.0`

### Files Modified
1. ✅ `pubspec.yaml` - Dependencies updated
2. ✅ `lib/app/theme.dart` - Moon Design removed
3. ✅ `lib/main.dart` - Imports cleaned up
4. ✅ `lib/shared/widgets/hux_showcase.dart` - Working examples created

## 🚀 Hux Components That Work

Based on testing Hux v1.2.0, here are the components that actually exist and work:

### 1. HuxCard ✅
Beautiful card component for content containers.

```dart
import 'package:hux/hux.dart';

HuxCard(
  child: Padding(
    padding: EdgeInsets.all(16),
    child: Column(
      children: [
        Text('Card Title'),
        Text('Card content goes here'),
      ],
    ),
  ),
)
```

**Use for:**
- Parking session cards
- Dashboard stat cards
- Profile information cards
- Payment history items

### 2. HuxButton ✅
Modern button component.

```dart
// Basic button
HuxButton(
  child: Text('Submit'),
  onPressed: () {},
)

// Button with icon
HuxButton(
  child: Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(Icons.add),
      SizedBox(width: 8),
      Text('Add Vehicle'),
    ],
  ),
  onPressed: () {},
)

// Disabled button
HuxButton(
  child: Text('Disabled'),
  onPressed: null,
)
```

**Use for:**
- Primary actions
- Form submissions
- Navigation buttons

### 3. HuxCheckbox ✅
Checkbox component.

```dart
HuxCheckbox(
  value: isChecked,
  onChanged: (value) {
    setState(() => isChecked = value ?? false);
  },
)
```

**Use for:**
- Terms acceptance
- Feature toggles
- Multi-select lists

### 4. HuxSwitch ✅
Toggle switch component.

```dart
HuxSwitch(
  value: isEnabled,
  onChanged: (value) {
    setState(() => isEnabled = value);
  },
)
```

**Use for:**
- Settings toggles
- Feature enable/disable
- Notification preferences

### 5. HuxAlert ✅
Alert/notification component with variants.

```dart
// Info alert
HuxAlert(
  variant: HuxAlertVariant.info,
  title: 'Information',
  message: 'This is an info message',
)

// Success alert
HuxAlert(
  variant: HuxAlertVariant.success,
  title: 'Success',
  message: 'پرداخت با موفقیت انجام شد!',
)

// Warning alert
HuxAlert(
  variant: HuxAlertVariant.warning,
  title: 'Warning',
  message: 'لطفاً بررسی کنید',
)

// Error alert
HuxAlert(
  variant: HuxAlertVariant.error,
  title: 'Error',
  message: 'خطایی رخ داده است',
)
```

**Use for:**
- Success/error messages
- Warnings
- Information banners

## ❌ What's NOT in Hux

These components don't exist in Hux v1.2.0. Use Material equivalents instead:

| Component | Use Instead |
|-----------|-------------|
| HuxTextField | `TextField` |
| HuxChip | `Chip` |
| HuxDivider | `Divider` |
| HuxProgressBar | `LinearProgressIndicator` |
| HuxAvatar | `CircleAvatar` |
| HuxBadge | `Badge` widget |

### Examples:

```dart
// Text Field
TextField(
  decoration: InputDecoration(
    labelText: 'Email',
    border: OutlineInputBorder(),
    prefixIcon: Icon(Icons.email),
  ),
)

// Chip
Chip(
  label: Text('فعال'),
  avatar: Icon(Icons.check_circle),
)

// Divider
Divider()

// Progress
LinearProgressIndicator(value: 0.7)

// Avatar
CircleAvatar(
  child: Text('AB'),
)

// Badge
Badge(
  label: Text('3'),
  child: Icon(Icons.notifications),
)
```

## 📱 View the Showcase

To see all working Hux components:

```dart
import 'package:your_app/shared/widgets/hux_showcase.dart';

// Navigate to:
Navigator.push(
  context,
  MaterialPageRoute(builder: (context) => HuxShowcase()),
);
```

## 🎯 Migration Strategy

### Recommended Approach:

1. **Use Hux for:**
   - Cards (HuxCard)
   - Buttons (HuxButton)
   - Alerts (HuxAlert)
   - Checkboxes/Switches (HuxCheckbox, HuxSwitch)

2. **Use Material for:**
   - Text fields
   - Chips
   - Dividers
   - Progress indicators
   - Avatars
   - Badges

3. **Mix and Match:**
   - Hux and Material components work perfectly together
   - Use Hux where it provides value
   - Use Material for everything else

### Example: Parking Session Card

```dart
HuxCard(
  child: Padding(
    padding: EdgeInsets.all(16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Title
        Text(
          'جلسه پارکینگ',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        
        SizedBox(height: 12),
        
        // Status chip (Material)
        Chip(
          label: Text('فعال'),
          avatar: Icon(Icons.local_parking, size: 18),
          backgroundColor: Colors.blue.withOpacity(0.1),
        ),
        
        SizedBox(height: 12),
        Divider(), // Material divider
        SizedBox(height: 12),
        
        // Info rows
        Row(
          children: [
            Icon(Icons.access_time, size: 16),
            SizedBox(width: 4),
            Text('2 ساعت و 30 دقیقه'),
          ],
        ),
        
        SizedBox(height: 16),
        
        // Action button (Hux)
        HuxButton(
          child: Text('پرداخت'),
          onPressed: () {},
        ),
      ],
    ),
  ),
)
```

## ✅ Verification

Run these commands to verify everything works:

```bash
# Install dependencies
flutter pub get

# Check for errors
flutter analyze

# Run the app
flutter run
```

## 📚 Resources

- **Hux Documentation**: https://docs.thehuxdesign.com/
- **Hux GitHub**: https://github.com/lofidesigner/hux
- **Hux pub.dev**: https://pub.dev/packages/hux
- **Showcase File**: `lib/shared/widgets/hux_showcase.dart`

## 💡 Tips

1. **Start Small**: Begin with one screen
2. **Test Both Themes**: Check light and dark mode
3. **RTL Support**: Verify Persian text displays correctly
4. **Mix Components**: Hux + Material = Perfect combination
5. **Don't Over-migrate**: Only use Hux where it adds value

## 🎨 Theme Integration

Hux components automatically respect your Material 3 theme:
- ✅ Color scheme
- ✅ Text theme
- ✅ Dark/Light mode
- ✅ RTL/LTR direction

No additional configuration needed!

## 🐛 Troubleshooting

### Import Error
```dart
// ✅ Correct
import 'package:hux/hux.dart';
```

### Component Not Found
If you get "undefined" errors, the component doesn't exist in Hux. Use Material equivalent.

### Styling Issues
Hux uses your app's theme. Check `lib/app/theme.dart` for theme configuration.

---

**Migration Complete! 🎉**

Your app now uses Hux UI for modern components while maintaining full compatibility with Material Design. The best of both worlds!
