# Shared UI screenshot goldens — Android (Robolectric)

These PNGs are the expected images for the **Android** suite, rendered on the host JVM by
Robolectric (no emulator or device). Desktop has its own goldens under
`shared/src/jvmTest/screenshots/`.

See [`docs/screenshot-regression.md`](../../../../docs/screenshot-regression.md) for the verify
and record commands, the per-image review checklist, the fixed render conditions, and limitations.

Quick reference:

```sh
./gradlew :shared:verifyScreenshots        # both platforms, read-only
./gradlew :shared:verifyAndroidScreenshots # Android only
./gradlew :shared:recordAndroidScreenshots # explicit re-record after review
```
