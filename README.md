# Manijero — Olive Grove Assistant

Manijero is a Kotlin Multiplatform app for people who own or manage one or more olive lands and want straightforward, source-backed help with agricultural questions. The MVP centers on an AI chat assistant and basic local management of multiple lands.

## Available platforms

- **Android**
- **Desktop (JVM)**
- **iOS:** (coming soon).

The intended user has little experience with computers or apps. The interface and assistant should use plain Spanish, clear next steps, readable text, and source links. Land information is local by default; only the minimum context needed for a question should be sent to the answer service.

For current scope and behavior, start with [AGENTS.md](AGENTS.md), [CONTEXT.md](CONTEXT.md), and the owning feature spec. The [build brief](docs/build-brief.md) and [MasterPlanV3.md](MasterPlanV3.md) are historical planning records.

## Project structure

- [`shared/src/commonMain`](shared/src/commonMain/kotlin): shared Kotlin business logic and Compose UI for Android/Desktop and later iOS reuse.
- [`androidApp`](androidApp): Android application entry point.
- [`shared`](shared/src): shared Kotlin and Compose code. Current targets are defined in Gradle.
- [`desktopApp`](desktopApp): Desktop launcher.
- `iosApp`: existing project scaffold; not part of MVP build/release acceptance.

Implement product behavior and Compose UI in shared `commonMain`. Keep platform integrations and app entry points in platform-specific source sets so a later iOS target can reuse the same UI and business logic.

## Using Manijero

### Start the backend

The client app needs the local FastAPI service running to send questions. From the repository root, start it with:

```sh
./scripts/init.sh --backend
```

On first run, the script creates `backend/.venv` and installs the backend requirements; later runs reuse that environment and check/install requirements. It starts the API with campaign `2026` unless `MANIJERO_ACTIVE_CAMPAIGN` is already set. The backend binds to `0.0.0.0` for Android emulator access through `http://10.0.2.2:8000`; this exposes the local development API on your network, so use a trusted network or set `MANIJERO_BACKEND_HOST=127.0.0.1` to restrict access to this computer. Leave that terminal open, then run `./scripts/init.sh --android` or `./scripts/init.sh --desktop` in another terminal. Desktop uses `http://127.0.0.1:8000`. Check the service at `http://127.0.0.1:8000/health`. Stop the backend with `Ctrl+C` when finished. For a physical Android device on the same trusted LAN, build with `-PmanijeroAskBaseUrl=http://<computer-lan-ip>:8000`.


### Running the client apps

Building and running:

```sh
./scripts/init.sh --android-run # builds, boots an emulator if needed, installs, and launches the app
./scripts/init.sh --desktop    # launches the Desktop app
```
When the service is running and reachable, the Android app is wired to the local service in `http://10.0.2.2:8000`; otherwise questions show the plain-Spanish failure notice with a `Reintentar` button. On Android 17, the app asks for local-network access on first launch; allow it so the app can reach the development backend.
The Desktop app is wired to the local service in `http://127.0.0.1:8000`. Besides that, the Desktop app keeps its lands in `~/.manijero/lands-v1.txt` (the filename is historical; the file holds the shared `land-store-v2` aggregate of active and removed lands, and an older `land-store-v1` file is migrated on first read); remove that file to start from an empty list.

### Build and verification

Standard verification (shared host tests + Android debug APK + Desktop build):

```sh
./scripts/init.sh --verify
```

## Product principles

- The assistant grounds legal or regulatory claims in approved official sources, cites them, and says when it cannot answer safely.
- Multiple lands are supported. Use all lands by default and ask the user to choose when the answer differs by land.
- Unknown land details stay unknown; stored details do not prove legal eligibility.
- Collect and transmit as little information as possible, and explain data handling in plain Spanish.

## Documentation

- [AGENTS.md](AGENTS.md): reading route and project rules.
- [PROGRESS.md](PROGRESS.md): current status, limitations, open checks, and verification tiers.
- [ARCHITECTURE.md](ARCHITECTURE.md), [CONTEXT.md](CONTEXT.md), [CONSTRAINTS.md](CONSTRAINTS.md), and [DESIGN.md](DESIGN.md): current boundaries, scope, durable rules, and UI guidance.
- Feature behavior lives in [specs](docs/specs/); accepted evidence lives in [validations](docs/validations/).
- [Contracts](contracts/) and [knowledge](knowledge/README.md) document the API and reviewed corpus formats.
- The [build brief](docs/build-brief.md) and [Master Plan v3](MasterPlanV3.md) are historical planning records.
