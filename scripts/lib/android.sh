# Android and Desktop builds and the emulator launch: --android, --android-run, --desktop, --android-qa, --desktop-qa.
run_android_on_emulator() {
  local sdk_root="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  local adb emulator apk="$REPO_ROOT/androidApp/build/outputs/apk/debug/androidApp-debug.apk"
  local serial avd booted=0 attempt
  adb="$sdk_root/platform-tools/adb"
  emulator="$sdk_root/emulator/emulator"

  if [[ -z "$sdk_root" || ! -x "$adb" ]]; then
    printf 'Android SDK adb not found. Set ANDROID_HOME (or ANDROID_SDK_ROOT) to your SDK path.\n' >&2
    return 1
  fi

  ./gradlew :androidApp:assembleDebug

  serial="$("$adb" devices | awk '$1 ~ /^emulator-/ && $2 == "device" { print $1; exit }')"
  if [[ -z "$serial" ]]; then
    if [[ ! -x "$emulator" ]]; then
      printf 'Android emulator executable not found at %s. Install the Android Emulator SDK package.\n' "$emulator" >&2
      return 1
    fi
    avd="$("$emulator" -list-avds | sed -n '1p')"
    if [[ -z "$avd" ]]; then
      printf 'No Android Virtual Device (AVD) is configured. Create one in Android Studio Device Manager, then rerun --android-run.\n' >&2
      return 1
    fi
    printf 'Starting emulator AVD: %s\n' "$avd"
    "$emulator" -avd "$avd" >/dev/null 2>&1 &

  fi

  for ((attempt = 0; attempt < 240; attempt++)); do
    serial="$("$adb" devices | awk '$1 ~ /^emulator-/ && $2 == "device" { print $1; exit }')"
    if [[ -n "$serial" ]] && [[ "$("$adb" -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
      booted=1
      break
    fi
    sleep 1
  done
  if (( booted == 0 )); then
    printf 'Timed out waiting for the Android emulator to finish booting. Check the emulator window and try again.\n' >&2
    return 1
  fi

  printf 'Installing app on %s\n' "$serial"
  "$adb" -s "$serial" install -r "$apk"
  "$adb" -s "$serial" shell monkey -p com.jamarglex.manijero 1
}

build_android() {
  ./gradlew :androidApp:assembleDebug
}

run_desktop() {
  ./gradlew :desktopApp:run
}

build_android_qa() {
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  ./gradlew :androidApp:assembleDebug -PmanijeroEnvironment=qa
  printf 'Result: the Manijero QA app was built: androidApp/build/outputs/apk/debug/androidApp-debug.apk\n'
}

run_desktop_qa() {
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  ./gradlew :desktopApp:run -PmanijeroEnvironment=qa
}
