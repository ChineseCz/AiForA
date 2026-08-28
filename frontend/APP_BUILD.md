# Android APK

This project uses Capacitor as a thin Android shell around the deployed web app.

The APK supports a right-edge swipe-left gesture and the Android system back button.
Both use the same in-app navigation rules. On the home page, the first back action
shows a confirmation and the second action within two seconds exits the app. After
changing frontend gesture code, run `npm run cap:sync` before rebuilding the APK.

## Configure the server

Set the public URL of the frontend before syncing the Android project:

```powershell
$env:CAP_SERVER_URL = "http://124.222.169.60/"
npm run cap:sync
```

For production, use an HTTPS URL and omit the `http`/cleartext setup after updating
`capacitor.config.ts`.

## Build a debug APK

Install JDK 17 or newer and Android Studio/Android SDK, then run:

```powershell
$env:CAP_SERVER_URL = "http://124.222.169.60/"
npm run cap:sync
.\android\gradlew.bat -p android assembleDebug
```

The debug APK is generated under:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

The current machine has Java 8, so Android compilation cannot run until a newer
JDK is installed and selected through `JAVA_HOME`.
