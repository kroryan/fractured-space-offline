# Fractured Space Offline

Juega a **Fractured Space** sin conexión, contra bots, con un servidor local que imita al servicio oficial (Fireline), cerrado desde 2019.

*English summary below.*

## Instalación (fácil)

1. Instala **Fractured Space** desde Steam. Es gratis y sigue disponible en las bibliotecas.
2. Descarga **`FracturedSpaceOfflineSetup.exe`** desde [Releases](https://github.com/kroryan/fractured-space-offline/releases/latest).
3. Ejecútalo. Comprueba que la carpeta del juego es la correcta (normalmente `...\steamapps\common\Space`; si no la detecta, pulsa *Examinar*) y pulsa **Instalar**.
4. Abre **Fractured Space Bootstrapper Offline** desde el menú Inicio o el escritorio.
5. En el juego: **Play → Training → Solo vs AI**.

El instalador:
- Aplica el parche del cliente al juego. Los archivos van dentro del propio instalador (carpeta `patch/` de este repositorio) y se comprueban por SHA-256. Guarda los originales en `<juego>\fractured-offline-backup`.
- Instala el lanzador en `%LOCALAPPDATA%\Programs\fractured-space-bootstrapper-offline`.
- Crea accesos directos y una entrada en *Configuración → Aplicaciones* para desinstalarlo. Al desinstalar puedes elegir si restaurar los archivos originales del juego.

Todo funciona sin internet: el instalador no descarga nada. No necesita permisos de administrador. Tampoco instala certificados ni toca el archivo `hosts`.

## Cómo funciona

```
FracturedSpaceBootstrapperOffline.exe
 ├─ servidor HTTP local en 127.0.0.1:8080  ← responde como api.fireteam.net (respuestas grabadas)
 └─ lanza "Fractured Space.exe" -flhost=http://127.0.0.1:8080 -discord=offline
```

- El juego necesita el servicio **Fireline** para iniciar sesión y cargar la cuenta, las naves y el progreso.
- El ejecutable parcheado de la comunidad acepta `-flhost` para usar otro servidor.
- El lanzador incluye un emulador mínimo que sirve respuestas grabadas del servicio original, basado en [Tigerhacker/refireline](https://github.com/Tigerhacker/refireline).
- Las peticiones del juego se guardan en `requests.log`. Las que no tienen respuesta grabada aparecen como `MISS`.

### Limitaciones
- La cuenta es una cuenta **grabada**: el progreso no se guarda entre sesiones.
- La tienda, las compras y el multijugador no funcionan.
- Para jugar online con la comunidad, usa el [Fractured Space Bootstrapper](https://github.com/Tigerhacker/fractured-bootstrapper). Los dos pueden convivir porque usan el mismo parche.

## Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `src/Launcher/OfflineLauncher.cs` | Lanzador con el servidor Fireline local integrado |
| `src/Installer/Installer.cs` | Instalador/desinstalador gráfico (aplica el parche e instala el lanzador) |
| `server/responses.json` | Respuestas grabadas de `api.fireteam.net` (de refireline) |
| `patch/` | Archivos del parche del cliente (ejecutable modificado, `BP.pak` y scripts de la interfaz) |
| `server/fireline_emu.py` | Versión alternativa del servidor en Python/Flask |
| `build.ps1` | Script de compilación |

## Compilar

Solo hace falta Windows: usa el compilador de C# que viene con .NET Framework 4.x.

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

El resultado es `dist\FracturedSpaceOfflineSetup.exe`, un único archivo que lleva dentro el lanzador, los datos y el parche.

### Servidor en Python (opcional)

```bash
pip install flask
python server/fireline_emu.py        # http://127.0.0.1:8080
```

Después, lanza el juego parcheado:

```bat
set SteamAppId=310380
"...\Space\spacegame\Binaries\Win64\Fractured Space.exe" -flhost=http://127.0.0.1:8080 -discord=offline
```

## Créditos y licencia

- [Tigerhacker/refireline](https://github.com/Tigerhacker/refireline): emulador de Fireline y respuestas grabadas (GPL-3.0).
- [Tigerhacker/fractured-bootstrapper](https://github.com/Tigerhacker/fractured-bootstrapper): origen del parche del cliente incluido en `patch/`.
- Este proyecto se distribuye bajo **GPL-3.0** (ver `LICENSE`).

Fractured Space es propiedad de sus respectivos dueños. Este proyecto no está afiliado a ellos. La carpeta `patch/` contiene archivos del cliente modificados por la comunidad, que se incluyen solo para preservar el juego.

---

## English summary

Play **Fractured Space** offline against bots.
1. Install the game from Steam.
2. Download `FracturedSpaceOfflineSetup.exe` from Releases.
3. Pick the game folder and click *Instalar*.
4. Start **Fractured Space Bootstrapper Offline**, then go to *Play → Training → Solo vs AI*.

How it works:
- The installer applies the client patch embedded in it (`patch/` folder, verified by SHA-256). No internet connection is needed.
- The launcher runs a tiny local Fireline emulator that serves recorded responses (based on refireline) and starts the game with `-flhost=http://127.0.0.1:8080`.
- Progress is not saved, and the store and multiplayer are unavailable.

Build with `build.ps1` (needs only the .NET Framework 4.x `csc.exe` that ships with Windows). License: GPL-3.0.
