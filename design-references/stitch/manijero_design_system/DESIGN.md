---
name: Manijero Design System
colors:
  surface: '#f9faf4'
  surface-dim: '#dadad5'
  surface-bright: '#f9faf4'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4ee'
  surface-container: '#eeeee9'
  surface-container-high: '#e8e9e3'
  surface-container-highest: '#e2e3dd'
  on-surface: '#1a1c19'
  on-surface-variant: '#424940'
  inverse-surface: '#2f312d'
  inverse-on-surface: '#f1f1eb'
  outline: '#72796f'
  outline-variant: '#c2c8bd'
  surface-tint: '#416741'
  primary: '#214624'
  on-primary: '#ffffff'
  primary-container: '#385e39'
  on-primary-container: '#abd6a7'
  inverse-primary: '#a7d2a3'
  secondary: '#7e562e'
  on-secondary: '#ffffff'
  secondary-container: '#fdc796'
  on-secondary-container: '#79512a'
  tertiary: '#602e40'
  on-tertiary: '#ffffff'
  tertiary-container: '#7b4557'
  on-tertiary-container: '#feb7cc'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#c2eebe'
  primary-fixed-dim: '#a7d2a3'
  on-primary-fixed: '#002106'
  on-primary-fixed-variant: '#294f2b'
  secondary-fixed: '#ffdcbf'
  secondary-fixed-dim: '#f1bc8c'
  on-secondary-fixed: '#2d1600'
  on-secondary-fixed-variant: '#633f19'
  tertiary-fixed: '#ffd9e2'
  tertiary-fixed-dim: '#f9b3c8'
  on-tertiary-fixed: '#360c1d'
  on-tertiary-fixed-variant: '#6a3748'
  background: '#f9faf4'
  on-background: '#1a1c19'
  surface-variant: '#e2e3dd'
typography:
  headline-xl:
    fontFamily: Source Serif 4
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  headline-xl-mobile:
    fontFamily: Source Serif 4
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
  headline-lg:
    fontFamily: Source Serif 4
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Source Sans 3
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Source Sans 3
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Source Sans 3
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-lg:
    fontFamily: Source Sans 3
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  label-md:
    fontFamily: Source Sans 3
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  caption:
    fontFamily: Source Sans 3
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  margin: 1.5rem
  space-xs: 0.375rem
  space-sm: 0.75rem
  space-md: 1.5rem
  space-lg: 2rem
  space-xl: 3rem
---

## Brand & Style

This design system establishes an agricultural and rustic modern aesthetic tailored for Manijero, an olive-grove assistant app designed for everyday agricultural work. The brand personality is grounded, dependable, warm, and highly approachable, evoking the traditional yet innovative spirit of Mediterranean olive cultivation. 

The UI bridges rural heritage with modern digital utility, utilizing a tactile, high-contrast visual style optimized for outdoor readability under direct sunlight. Typography and interactive elements are built with generous proportions to support users with low digital confidence, ensuring effortless navigation in the field.

## Colors

The palette is rooted in the natural landscape of the olive grove. 
- **Primary:** Deep olive green (`#385E39`) establishes the core identity, providing high contrast and visual stability.
- **Secondary:** Warm earth brown (`#8C6239`) roots the interface, representing rich soil and traditional wooden tools.
- **Tertiary:** Sun-baked amber (`#D9A036`) serves as an accent for actionable highlights, warnings, and ripe fruit indicators.
- **Neutral:** Limestone cream (`#F4F1EA`) acts as the primary background surface, replacing harsh stark whites to reduce glare outdoors.

## Typography

Typography balances authoritative editorial warmth with extreme legibility. **Source Serif 4** provides a grounded, trustworthy voice for headlines, while **Source Sans 3** delivers crisp, unobstructed clarity for body copy and interactive labels. 

Sizes are scaled generously to accommodate outdoor glare and quick scanning while operating machinery or tending trees. Avoid using font sizes below 14px in any primary workflows to maintain accessibility.

## Layout & Spacing

The layout utilizes a structured 12-column fluid grid system optimized for rugged mobile devices and ruggedized tablets used in the field. 

- **Gutters & Margins:** Generous 24px (`1.5rem`) margins and gutters prevent accidental edge-touches and account for thumb zones when holding a device outdoors with one hand.
- **Rhythm:** The spacing scale is intentionally amplified (`space-md` is 24px) to ensure clear visual separation between interactive cards and data groups, preventing cognitive overload for users with low digital confidence.

## Elevation & Depth

Depth is conveyed through tactile, low-contrast structural cues rather than complex floating shadows. 

- **Surface Layers:** Utilize solid tonal layers shifting subtly between the limestone cream background and pure white container cards.
- **Outlines:** Employ distinct, high-contrast borders using the earth brown or dark olive tones to define clickable areas clearly. Avoid ambiguous ghost borders.
- **Shadows:** Restrict ambient shadows to prominent floating action buttons or active sticky bottom bars, using diffused, warm-tinted shadows that mimic natural sunlight drop-off.

## Shapes

The shape language relies on a friendly, approachable roundedness level (`2`, providing balanced, moderately soft curves). 

UI containers, cards, and input fields feature clean, tactile corners that feel approachable while maintaining a structured, reliable aesthetic. Larger containers scale up smoothly, while interactive buttons maintain comfortable, friendly radii to signal clear touch targets.

## Components

- **Buttons:** Designed with large touch targets (minimum 48px height). Primary buttons use solid olive green with bold text; secondary buttons use earth brown outlines with solid backgrounds. Always include clear iconography alongside plain Spanish text (e.g., "Regar ahora" with a water drop icon).
- **Cards:** Used to group grove metrics (weather, irrigation status, harvest yield). Styled with limestone backgrounds, distinct earth-brown borders, and generous internal padding.
- **Input Fields:** High-contrast text fields with thick borders and clear, persistent floating labels in plain Spanish. Focus states must display a high-visibility sun-baked amber ring.
- **Checkboxes & Radio Buttons:** Oversized tap targets with clear visual checkmarks and high-contrast fill states to accommodate outdoor work environments.
- **Chips:** Used for quick-filtering tasks (e.g., "Poda", "Riego", "Abono"). Pill-shaped elements with high contrast text and distinct active states.
- **Lists:** Generously spaced list items with clear dividing lines, large icons, and distinct chevron indicators for navigation.