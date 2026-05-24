# Hux UI - Quick Start Guide

## 🎉 Migration Complete!

Moon Design has been successfully replaced with **Hux UI v1.2.0** - a modern, state-of-the-art UI library for Flutter.

## 📦 What's Included

### Example Files (Ready to Use!)

1. **Component Showcase** (`lib/shared/widgets/hux_components_showcase.dart`)
   - Complete demonstration of all Hux components
   - Buttons, Cards, Text Fields, Chips, Badges, Switches, Progress Bars, Avatars, Alerts, and more
   - Copy-paste ready examples

2. **Parking Session Card** (`lib/features/home/widgets/parking_session_card_hux.dart`)
   - Real-world example using Hux components
   - Modern parking session display with status chips
   - Demonstrates Hux Card, Chip, Divider, and Button components

3. **Dashboard Stats** (`lib/features/home/widgets/dashboard_stats_hux.dart`)
   - Beautiful dashboard with statistics
   - Gradient cards, stat cards with trends
   - Activity timeline with Hux components

## 🚀 Quick Usage

### Import Hux
```dart
import 'package:hux/hux.dart';
```

### Basic Examples

#### Button
```dart
HuxButton(
  text: 'ثبت',
  icon: Icons.check,
  onPressed: () {},
  type: HuxButtonType.primary,
)
```

#### Card
```dart
HuxCard(
  elevation: 2,
  borderRadius: 16,
  child: Padding(
    padding: EdgeInsets.all(16),
    child: Text('محتوای کارت'),
  ),
)
```

#### Text Field
```dart
HuxTextField(
  label: 'ایمیل',
  hint: 'ایمیل خود را وارد کنید',
  prefixIcon: Icons.email,
  onChanged: (value) {},
)
```

#### Chip
```dart
HuxChip(
  label: 'فعال',
  icon: Icons.check_circle,
  type: HuxChipType.filled,
  onTap: () {},
)
```

#### Badge
```dart
HuxBadge(
  child: Icon(Icons.notifications),
  value: '5',
)
```

## 📱 View Examples

To see all components in action, navigate to the showcase screen in your app or check the example files mentioned above.

## 🎨 Styling

Hux components automatically adapt to your Material 3 theme. They respect:
- Color scheme (primary, secondary, error, etc.)
- Text theme
- Dark/Light mode
- RTL/LTR direction

## 🔄 Migration Strategy

### Phase 1: ✅ Complete
- Dependencies updated
- Moon Design removed
- Hux installed and ready

### Phase 2: Gradual Component Migration (Optional)
You can gradually replace Material widgets with Hux components:

| Material Widget | Hux Component |
|----------------|---------------|
| `ElevatedButton` | `HuxButton(type: HuxButtonType.primary)` |
| `OutlinedButton` | `HuxButton(type: HuxButtonType.outlined)` |
| `TextButton` | `HuxButton(type: HuxButtonType.text)` |
| `Card` | `HuxCard` |
| `TextField` | `HuxTextField` |
| `Chip` | `HuxChip` |
| `Switch` | `HuxSwitch` |
| `Checkbox` | `HuxCheckbox` |

### Phase 3: Custom Components
Create your own Hux-based components for:
- Vehicle displays
- Parking status indicators
- Payment cards
- Session timers

## 💡 Tips

1. **Start Small**: Begin with one screen (e.g., settings or profile)
2. **Mix and Match**: Hux works alongside Material widgets
3. **Customize**: All Hux components are highly customizable
4. **Test Both Themes**: Check light and dark mode
5. **RTL Support**: Verify Persian text displays correctly

## 📚 Resources

- **Hux Documentation**: https://docs.thehuxdesign.com/
- **Hux GitHub**: https://github.com/lofidesigner/hux
- **Hux pub.dev**: https://pub.dev/packages/hux
- **Example Files**: Check the files listed above

## 🐛 Troubleshooting

### Import Error
```dart
// ✅ Correct
import 'package:hux/hux.dart';

// ❌ Wrong
import 'package:moon_design/moon_design.dart';
```

### Component Not Found
Make sure you've run:
```bash
flutter pub get
```

### Styling Issues
Hux components use your app's theme. Check your `AppTheme` configuration in `lib/app/theme.dart`.

## 🎯 Next Steps

1. ✅ Review the example files
2. ✅ Run the app to see Hux in action
3. ✅ Choose a screen to migrate
4. ✅ Replace Material widgets with Hux components
5. ✅ Test and iterate

## 📝 Notes

- **No Breaking Changes**: Your existing code continues to work
- **Incremental Migration**: Migrate at your own pace
- **Better Design**: Hux provides modern, consistent UI
- **Fully Compatible**: Works with Material 3, Riverpod, and all your existing packages

---

**Happy Coding! 🚀**

For questions or issues, refer to the Hux documentation or check the example files in this project.
