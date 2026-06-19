# Powerfin POS — APK Android con WebView

> Documento de diseño. Implementar lunes 23-jun-2026.
> Resuelve: PWA no instalable en Android sin certificado SSL válido.

---

## Problema

- El servidor está en LAN privada (`192.168.1.25`), sin dominio público
- Sin SSL válido → Chrome en Android **no habilita** instalación PWA
- Let's Encrypt imposible (no hay exposición a internet)
- Solo permite "Agregar a inicio" como bookmark (barra de navegador visible, sin service worker)

---

## Solución

**APK mínimo con WebView** que carga `http://192.168.1.25:5173`. 
Una sola Activity, ~40 líneas de código. Se genera el APK **una vez** y se instala en los dispositivos.

### Lo que NO necesitamos

- ❌ SSL / certificados
- ❌ Google Play Store
- ❌ Play Console ($25 USD)
- ❌ Tauri / Pake / Rust (overkill)
- ❌ Firebase / notificaciones push
- ❌ Cámara / GPS / APIs nativas

---

## Arquitectura

```
┌─────────────────────────────────────┐
│  APK Powerfin POS  (3-5 MB)         │
│  ┌───────────────────────────────┐  │
│  │  WebView                      │  │
│  │  http://192.168.1.25:5173    │  │
│  │                               │  │
│  │  ← carga el POS directamente  │  │
│  │    del servidor               │  │
│  └───────────────────────────────┘  │
│  Java/Kotlin wrapper (~40 líneas)   │
└─────────────────────────────────────┘
          │
          ▼
┌─────────────────┐
│  Servidor :5173  │  ← POS SvelteKit (npm run dev)
│  192.168.1.25   │     Sin cambios
└─────────────────┘
```

- El APK solo es el cascarón. El POS se sirve siempre del backend
- Cualquier cambio en `pos/src/` → visible al instante (sin regenerar APK)
- Navegación, HMR, SSE — todo funciona igual que en Chrome

---

## Estructura del proyecto Android

```
pos-apk/
├── app/
│   ├── build.gradle                    # compileSdk 34, minSdk 26 (Android 8+)
│   └── src/main/
│       ├── AndroidManifest.xml         # permisos: INTERNET, fullscreen
│       ├── java/com/powerfin/pos/
│       │   └── MainActivity.java       # WebView + config
│       └── res/
│           ├── mipmap-*/ic_launcher.png  # ícono de la app
│           └── values/
│               ├── strings.xml         # "Powerfin POS"
│               └── themes.xml          # sin ActionBar
├── build.gradle                        # project-level
├── gradle.properties
└── settings.gradle
```

---

## MainActivity.java (pseudocódigo)

```java
package com.powerfin.pos;

import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {
    private static final String POS_URL = "http://192.168.1.25:5173";
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.setWebViewClient(new WebViewClient());
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setUserAgentString(
            settings.getUserAgentString() + " PowerfinPOS/1.0"
        );

        webView.loadUrl(POS_URL);
        setContentView(webView);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
```

---

## AndroidManifest.xml (pseudocódigo)

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:allowBackup="false"
        android:fullBackupContent="false"
        android:label="Powerfin POS"
        android:icon="@mipmap/ic_launcher"
        android:theme="@style/Theme.PowerfinPOS"
        android:usesCleartextTraffic="true">   <!-- permite HTTP sin SSL -->

        <activity
            android:name=".MainActivity"
            android:configChanges="orientation|screenSize"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

---

## ⚠️ Puntos clave del AndroidManifest

| Atributo | Valor | Por qué |
|----------|-------|---------|
| `usesCleartextTraffic` | `true` | Permite HTTP (sin SSL) |
| `configChanges` | `orientation\|screenSize` | Evita recrear la Activity al rotar |
| `allowBackup` | `false` | No guarda cookies/tokens en backup Android |
| `INTERNET` | ✔️ | Obvio |

---

## Cómo compilar (en dev)

### Opción 1 — Con Android Studio (recomendado)

```bash
# Instalar Android Studio desde https://developer.android.com
# Abrir pos-apk/ como proyecto
# Build → Build Bundle(s) / APK(s) → Build APK(s)
# El APK sale en pos-apk/app/build/outputs/apk/debug/app-debug.apk
```

### Opción 2 — Línea de comandos (sin IDE)

```bash
# Requisitos: Java 17+, Android SDK command-line tools
cd pos-apk
./gradlew assembleDebug
# APK en app/build/outputs/apk/debug/app-debug.apk
```

---

## Cómo instalar en los dispositivos

### Por USB (adb)

```bash
adb install app-debug.apk
```

### Por descarga directa

```bash
# Subir el APK al servidor para que los dispositivos lo descarguen
scp app-debug.apk app@192.168.1.25:/opt/powerfin/pos/pos-apk/
# Acceder desde el dispositivo Android a:
# http://192.168.1.25/pos-apk/app-debug.apk
# (requiere servir la carpeta estática en Nginx)
```

### Por transferencia de archivos

```
Pasar el APK al celular por cable USB, WhatsApp, o cualquier medio.
Abrir el archivo .apk → Instalar → Aceptar "Orígenes desconocidos".
```

---

## Lo que el usuario final ve

```
1. Instala el APK (una sola vez)
2. Abre "Powerfin POS" desde el home
3. Pantalla completa, sin barra de navegador
4. Login normal con PIN
5. Flujo de venta idéntico al navegador
6. SSE, impresión, todo funciona igual
```

---

## Mantenimiento

- **Cambios en el POS:** Cero acción. Se reflejan al instante (el APK carga del servidor).
- **Cambios en la IP del servidor:** Editar `POS_URL` en `MainActivity.java`, recompilar, reinstalar.
- **Nuevas versiones de Android:** Compatible desde Android 8 (2017) hasta Android 15 (2025).
- **Sin dependencias externas:** Solo Android SDK estándar, nada de terceros.

---

## No implementar

- ❌ React Native / Flutter — innecesario para un WebView
- ❌ Actualizaciones OTA del APK — no cambia nunca
- ❌ Múltiples activities / navegación nativa — solo WebView
- ❌ Notificaciones push — el POS no las necesita
- ❌ Login biométrico — el POS ya tiene PIN
