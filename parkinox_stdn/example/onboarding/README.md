# V2Ray Onboarding Screen

This directory contains the introduction animation onboarding screen for the V2Ray VPN app.

## Structure

- `introduction_animation_screen.dart` - Main onboarding screen with animation controller
- `components/` - Individual animated view components:
  - `splash_view.dart` - Initial welcome screen
  - `relax_view.dart` - Fast & Reliable feature screen
  - `care_view.dart` - Privacy First feature screen
  - `mood_diary_view.dart` - Easy to Use feature screen
  - `welcome_view.dart` - Final ready to go screen
  - `top_back_skip_view.dart` - Navigation controls (back/skip buttons)
  - `center_next_button.dart` - Next button with progress indicators

## Features

- Smooth slide transitions between screens
- Progress indicators showing current step
- Back/Skip navigation controls
- Animated button that expands to "Get Started" on final screen
- Login prompt at the bottom

## Animation Timeline

The animation controller runs for 8 seconds with the following intervals:

- **0.0 - 0.2**: Splash view slides out, first feature slides in
- **0.2 - 0.4**: Second feature slides in
- **0.4 - 0.6**: Third feature slides in
- **0.6 - 0.8**: Fourth feature slides in, button expands
- **0.8 - 1.0**: Final welcome screen

## Usage

The onboarding screen is set as the home screen in `main.dart`. After completing the onboarding, users are navigated to the main app.

## Assets Required

Make sure these image assets are available in `assets/introduction_animation/`:
- `introduction_image.png`
- `relax_image.png`
- `care_image.png`
- `mood_dairy_image.png`
- `welcome.png`

Add these to your `pubspec.yaml` under assets section.
HELLO MY NAME IS ERFAN 