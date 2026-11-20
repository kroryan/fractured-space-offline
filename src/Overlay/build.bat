@echo off
setlocal
rem Builds build\fso_offline_menu.dll (the in-game F1 menu) with MSVC.
rem Needs Visual Studio Build Tools with "Desktop development with C++".

if defined VCINSTALLDIR goto :have_msvc
set "VSINSTALLERDIR=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
if not exist "%VSINSTALLERDIR%\vswhere.exe" (
  echo ERROR: vswhere.exe not found. Install Visual Studio Build Tools with C++.
  exit /b 1
)
pushd "%VSINSTALLERDIR%"
for /f "usebackq tokens=*" %%i in (`.\vswhere.exe -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSPATH=%%i"
popd
if not defined VSPATH (
  echo ERROR: no Visual Studio installation with the C++ x64 toolset was found.
  exit /b 1
)
call "%VSPATH%\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
:have_msvc

set "ROOT=%~dp0"
set "TP=%ROOT%third_party"
set "MHROOT=%TP%"
set "MH=%MHROOT%\minhook"
set "OUT=%ROOT%build"
if not exist "%OUT%" mkdir "%OUT%"
pushd "%OUT%" || exit /b 1
if exist fso_offline_menu.dll del /f fso_offline_menu.dll

cl /nologo /c /O2 /MT /W3 /D_CRT_SECURE_NO_WARNINGS /DWIN32_LEAN_AND_MEAN /I"%MH%\include" ^
   "%MH%\src\buffer.c" "%MH%\src\hook.c" "%MH%\src\trampoline.c" "%MH%\src\hde\hde64.c" ^
   || (echo ERROR: compiling MinHook failed & popd & exit /b 1)

cl /nologo /c /O2 /MT /W3 /EHsc /std:c++17 /utf-8 /D_CRT_SECURE_NO_WARNINGS /DWIN32_LEAN_AND_MEAN ^
   /I"%TP%" /I"%TP%\imgui" /I"%MHROOT%" ^
   "%TP%\imgui\imgui.cpp" "%TP%\imgui\imgui_draw.cpp" "%TP%\imgui\imgui_widgets.cpp" ^
   "%TP%\imgui\imgui_impl_dx11.cpp" "%TP%\imgui\imgui_impl_win32.cpp" ^
   "%TP%\kiero\kiero.cpp" "%ROOT%fso_menu.cpp" ^
   || (echo ERROR: compiling the menu failed & popd & exit /b 1)

link /nologo /DLL /OUT:fso_offline_menu.dll ^
     fso_menu.obj imgui.obj imgui_draw.obj imgui_widgets.obj imgui_impl_dx11.obj imgui_impl_win32.obj kiero.obj ^
     buffer.obj hook.obj trampoline.obj hde64.obj ^
     kernel32.lib user32.lib gdi32.lib d3d11.lib dxgi.lib d3dcompiler.lib winhttp.lib imm32.lib ^
     || (echo ERROR: linking failed & popd & exit /b 1)

if not exist fso_offline_menu.dll (echo ERROR: no dll produced & popd & exit /b 1)
echo Built %OUT%\fso_offline_menu.dll
popd
exit /b 0
