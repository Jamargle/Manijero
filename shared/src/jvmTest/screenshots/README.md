# Shared UI screenshot goldens — Desktop

These PNGs are the expected images for the **Compose Desktop (JVM)** suite. Android has its own
goldens under `shared/src/androidHostTest/screenshots/`.

See [`docs/screenshot-regression.md`](../../../../docs/screenshot-regression.md) for the verify
and record commands, the per-image review checklist, the fixed render conditions, and limitations.

Quick reference:

```sh
./gradlew :shared:verifyScreenshots         # both platforms, read-only
./gradlew :shared:verifyDesktopScreenshots  # Desktop only
./gradlew :shared:recordDesktopScreenshots  # explicit re-record after review
```
