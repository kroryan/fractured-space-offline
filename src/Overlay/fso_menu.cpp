// Fractured Space Offline - in-game menu (F1).
//
// Loaded into the player's client by the battle-server mod's wer.dll, only
// when Fractured Space Offline started the game (FSO_OFFLINE_MENU=<port>:<token>
// in the environment). It draws an ImGui window on the game's own DirectX 11
// frame and sends every action to the launcher's loopback endpoint, which
// does the work through the local server's admin API.
//
// Hooks: IDXGISwapChain::Present / ResizeBuffers (kiero + MinHook) and the
// game window's WndProc (F1 toggle; input goes to the menu while it is open).

#include <windows.h>
#include <winhttp.h>
#include <d3d11.h>
#include <dxgi.h>

#include <cstdarg>
#include <cstdio>
#include <atomic>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "kiero/kiero.h"
#include "minhook/include/MinHook.h"
#include "imgui/imgui.h"
#include "imgui/imgui_impl_dx11.h"
#include "imgui/imgui_impl_win32.h"

extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND, UINT, WPARAM, LPARAM);

typedef HRESULT(__stdcall *PresentFn)(IDXGISwapChain *, UINT, UINT);
typedef HRESULT(__stdcall *ResizeBuffersFn)(IDXGISwapChain *, UINT, UINT, UINT, DXGI_FORMAT, UINT);

static PresentFn g_oPresent;
static ResizeBuffersFn g_oResize;
static WNDPROC g_oWndProc;
static HWND g_window;
static ID3D11Device *g_device;
static ID3D11DeviceContext *g_context;
static ID3D11RenderTargetView *g_rtv;
static bool g_ready;
static std::atomic<bool> g_open{false};
static DWORD g_startTick;

static int g_port;
static std::wstring g_token;
static bool g_es;

static std::mutex g_mu;
static std::string g_status = "...";
static std::string g_result;
static std::atomic<bool> g_busy{false};
static DWORD g_lastRefresh;

static const char *T(const char *en, const char *es) { return g_es ? es : en; }

static void MenuLog(const char *fmt, ...) {
  char dir[MAX_PATH];
  DWORD n = GetEnvironmentVariableA("LOCALAPPDATA", dir, MAX_PATH);
  if (n == 0 || n >= MAX_PATH - 64)
    return;
  strcat_s(dir, "\\FracturedSpaceOffline\\menu-loader.log");
  FILE *f = NULL;
  if (fopen_s(&f, dir, "a") != 0 || !f)
    return;
  fprintf(f, "pid %lu: ", GetCurrentProcessId());
  va_list ap;
  va_start(ap, fmt);
  vfprintf(f, fmt, ap);
  va_end(ap);
  fputc('\n', f);
  fclose(f);
}

// ---------------------------------------------------------------- launcher link

static std::string Http(const wchar_t *method, const std::wstring &path) {
  std::string body;
  HINTERNET s = WinHttpOpen(L"Fractured SpaceOfflineMenu", WINHTTP_ACCESS_TYPE_NO_PROXY, NULL, NULL, 0);
  if (!s)
    return "";
  WinHttpSetTimeouts(s, 3000, 3000, 30000, 120000);
  HINTERNET c = WinHttpConnect(s, L"127.0.0.1", (INTERNET_PORT)g_port, 0);
  HINTERNET r = c ? WinHttpOpenRequest(c, method, path.c_str(), NULL, NULL, NULL, 0) : NULL;
  if (r && WinHttpSendRequest(r, WINHTTP_NO_ADDITIONAL_HEADERS, 0, NULL, 0, 0, 0) &&
      WinHttpReceiveResponse(r, NULL)) {
    DWORD n = 0;
    while (WinHttpQueryDataAvailable(r, &n) && n > 0) {
      std::string chunk(n, '\0');
      DWORD got = 0;
      if (!WinHttpReadData(r, &chunk[0], n, &got) || got == 0)
        break;
      body.append(chunk.data(), got);
    }
  }
  if (r)
    WinHttpCloseHandle(r);
  if (c)
    WinHttpCloseHandle(c);
  WinHttpCloseHandle(s);
  return body;
}

static void RefreshStatus() {
  std::string st = Http(L"GET", L"/status?t=" + g_token);
  std::lock_guard<std::mutex> l(g_mu);
  g_status = st.empty() ? T("Fractured Space Offline launcher not reachable.", "No se encuentra el launcher de Fractured Space Offline.") : st;
}

static void RunAction(const std::wstring &query) {
  if (g_busy.exchange(true))
    return;
  {
    std::lock_guard<std::mutex> l(g_mu);
    g_result = T("Working...", "Aplicando...");
  }
  std::thread([query]() {
    std::string res = Http(L"POST", L"/action?t=" + g_token + L"&" + query);
    {
      std::lock_guard<std::mutex> l(g_mu);
      g_result = res.empty() ? T("No answer from the launcher.", "El launcher no responde.") : res;
    }
    RefreshStatus();
    g_busy = false;
  }).detach();
}

static void Act(const wchar_t *name) { RunAction(std::wstring(L"name=") + name); }

// Co-op host: join requests waiting for an answer (id, label).
struct JoinReq {
  std::string id, label;
};
static std::vector<JoinReq> g_requests;
static std::atomic<bool> g_hasRequests{false};

static DWORD WINAPI PollRequests(LPVOID) {
  for (;;) {
    std::string body = Http(L"GET", L"/requests?t=" + g_token);
    std::vector<JoinReq> list;
    size_t pos = 0;
    while (pos < body.size()) {
      size_t nl = body.find('\n', pos);
      std::string line = body.substr(pos, nl == std::string::npos ? std::string::npos : nl - pos);
      pos = nl == std::string::npos ? body.size() : nl + 1;
      size_t tab = line.find('\t');
      if (tab != std::string::npos)
        list.push_back({line.substr(0, tab), line.substr(tab + 1)});
    }
    {
      std::lock_guard<std::mutex> l(g_mu);
      g_requests = list;
    }
    g_hasRequests = !list.empty();
    Sleep(3000);
  }
}

// ---------------------------------------------------------------- UI

static void ApplyStyle(float scale) {
  ImGuiStyle &s = ImGui::GetStyle();
  ImGui::StyleColorsDark();
  s.WindowRounding = 6;
  s.FrameRounding = 4;
  s.GrabRounding = 4;
  s.WindowPadding = ImVec2(16, 14);
  s.FramePadding = ImVec2(10, 6);
  s.ItemSpacing = ImVec2(8, 8);
  s.WindowBorderSize = 1;
  ImVec4 *c = s.Colors;
  c[ImGuiCol_WindowBg] = ImVec4(0.07f, 0.09f, 0.12f, 0.96f);
  c[ImGuiCol_TitleBg] = c[ImGuiCol_TitleBgActive] = ImVec4(0.10f, 0.13f, 0.18f, 1.0f);
  c[ImGuiCol_Border] = ImVec4(0.35f, 0.78f, 1.0f, 0.45f);
  c[ImGuiCol_Button] = ImVec4(0.16f, 0.22f, 0.30f, 1.0f);
  c[ImGuiCol_ButtonHovered] = ImVec4(0.22f, 0.50f, 0.70f, 1.0f);
  c[ImGuiCol_ButtonActive] = ImVec4(0.35f, 0.78f, 1.0f, 1.0f);
  c[ImGuiCol_FrameBg] = ImVec4(0.12f, 0.16f, 0.22f, 1.0f);
  c[ImGuiCol_Separator] = ImVec4(0.35f, 0.78f, 1.0f, 0.35f);
  c[ImGuiCol_Text] = ImVec4(0.90f, 0.93f, 0.97f, 1.0f);
  s.ScaleAllSizes(scale);
}

static void Section(const char *title) {
  ImGui::Spacing();
  ImGui::TextColored(ImVec4(0.35f, 0.78f, 1.0f, 1.0f), "%s", title);
  ImGui::Separator();
}

static bool Btn(const char *label, float w) { return ImGui::Button(label, ImVec2(w, 0)); }

static char g_inCredits[16], g_inGP[16], g_inXP[16];

static void DrawMenu() {
  ImGuiIO &io = ImGui::GetIO();
  float fs = ImGui::GetFontSize();
  ImGui::SetNextWindowSize(ImVec2(fs * 40, io.DisplaySize.y * 0.88f), ImGuiCond_Always);
  ImGui::SetNextWindowPos(ImVec2(io.DisplaySize.x * 0.5f, io.DisplaySize.y * 0.5f), ImGuiCond_FirstUseEver, ImVec2(0.5f, 0.5f));
  bool keep = true;
  ImGui::Begin(T("FRACTURED SPACE OFFLINE  -  F1###dnmenu", "FRACTURED SPACE OFFLINE  -  F1###dnmenu"), &keep,
               ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoSavedSettings);
  if (!keep)
    g_open = false;

  if (GetTickCount() - g_lastRefresh > 4000 && !g_busy) {
    g_lastRefresh = GetTickCount();
    std::thread(RefreshStatus).detach();
  }
  std::string status, result;
  {
    std::lock_guard<std::mutex> l(g_mu);
    status = g_status;
    result = g_result;
  }
  ImGui::TextWrapped("%s", status.c_str());

  float avail = ImGui::GetContentRegionAvail().x;
  float w3 = (avail - ImGui::GetStyle().ItemSpacing.x * 2) / 3;

  std::vector<JoinReq> reqs;
  {
    std::lock_guard<std::mutex> l(g_mu);
    reqs = g_requests;
  }
  if (!reqs.empty()) {
    Section(T("Players asking to join your game", "Jugadores que piden unirse a tu partida"));
    for (const JoinReq &q : reqs) {
      ImGui::AlignTextToFramePadding();
      ImGui::TextUnformatted(q.label.c_str());
      ImGui::SameLine(avail - w3 * 2 / 3 * 2 - ImGui::GetStyle().ItemSpacing.x);
      std::string a = std::string(T("Accept", "Aceptar")) + "##a" + q.id;
      std::string d = std::string(T("Reject", "Rechazar")) + "##d" + q.id;
      std::wstring wid(q.id.begin(), q.id.end());
      ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.16f, 0.45f, 0.28f, 1.0f));
      if (Btn(a.c_str(), w3 * 2 / 3))
        RunAction(L"name=approve&id=" + wid);
      ImGui::PopStyleColor();
      ImGui::SameLine();
      if (Btn(d.c_str(), w3 * 2 / 3))
        RunAction(L"name=deny&id=" + wid);
    }
  }

  Section(T("Local match", "Partida local"));
  if (Btn(T("Toggle player god mode", "Activar/desactivar invulnerabilidad"), avail)) Act(L"god_player");
  if (Btn(T("Toggle allied bot god mode", "Invulnerabilidad de bots aliados"), avail)) Act(L"god_allies");
  if (Btn(T("Toggle enemy bot god mode", "Invulnerabilidad de bots enemigos"), avail)) Act(L"god_enemies");
  static int selectedShip = 0;
  static const char* ships[] = {"Aegis", "Basilisk", "Black Widow", "Brawler", "Centurion", "Colossus", "Destroyer", "Displacer", "Disruptor", "Endeavor", "Enforcer", "Equalizer", "Executioner", "Furion", "Ghost", "Gladiator", "Guardian", "Hunter", "Infiltrator", "Interceptor", "Leviathan", "Overseer", "Paladin", "Paragon", "Persecutor", "Pioneer", "Protector", "Punisher", "Raider", "Ranger", "Raven", "Reaper", "Sentinel", "Superlifter", "Venturer", "Watchman"};
  ImGui::Combo(T("Ship", "Nave"), &selectedShip, ships, IM_ARRAYSIZE(ships));
  if (Btn(T("Spawn allied ship", "Crear nave aliada"), avail)) {
    std::string name(ships[selectedShip]); RunAction(L"name=spawn_ally&ship=" + std::wstring(name.begin(),name.end()));
  }
  if (Btn(T("Spawn enemy ship", "Crear nave enemiga"), avail)) {
    std::string name(ships[selectedShip]); RunAction(L"name=spawn_enemy&ship=" + std::wstring(name.begin(),name.end()));
  }
  Section(T("Credits", "Créditos"));
  if (Btn("+100,000", avail)) Act(L"credits_100k");
  if (Btn(T("Maximum credits", "Créditos al máximo"), avail)) Act(L"credits_max");
  Section(T("Offline profile", "Perfil offline"));
  if (Btn(T("Unlock all ships", "Desbloquear todas las naves"), avail)) Act(L"unlock_ships");
  if (Btn(T("Restore level 68", "Restaurar nivel 68"), avail)) Act(L"level_68");
  Section(T("Personal statistics", "Estadísticas personales"));
  static bool confirmReset = false;
  ImGui::Checkbox(T("Confirm statistics reset", "Confirmar borrado de estadísticas"), &confirmReset);
  if (Btn(T("Reset my statistics", "Borrar mis estadísticas"), avail) && confirmReset) {
    Act(L"reset_stats"); confirmReset = false;
  }
  ImGui::TextWrapped("%s", T("Profile changes apply on the next login. Ships and level are separate from combat statistics.",
    "Los cambios se aplican al volver a entrar. Las naves y el nivel son independientes de las estadísticas de combate."));
  ImGui::Spacing();
  if (!result.empty())
    ImGui::TextWrapped("%s", result.c_str());
  ImGui::TextDisabled("%s", T("F1: show / hide. If the hangar does not refresh, open another screen and come back.",
                              "F1: mostrar / ocultar. Si el hangar no se actualiza, cambia de pantalla y vuelve."));
  ImGui::End();
}

static void DrawHint() {
  // A small reminder for the first seconds of each session, like the
  // revival's "(F1 to show/hide)" window; and, for a co-op host, a banner
  // while someone is waiting to join.
  bool early = GetTickCount() - g_startTick <= 25000;
  if (!early && (!g_hasRequests || g_open))
    return;
  ImGui::SetNextWindowPos(ImVec2(12, 12), ImGuiCond_Always);
  ImGui::SetNextWindowBgAlpha(0.75f);
  ImGui::Begin("##dnhint", NULL,
               ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoInputs |
                   ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoFocusOnAppearing | ImGuiWindowFlags_NoNav);
  if (g_hasRequests && !g_open) {
    std::string who;
    {
      std::lock_guard<std::mutex> l(g_mu);
      for (const JoinReq &q : g_requests)
        who += (who.empty() ? "" : ", ") + q.label;
    }
    ImGui::TextColored(ImVec4(0.45f, 0.95f, 0.55f, 1.0f), "%s %s  -  %s", T("Wants to join:", "Quiere unirse:"), who.c_str(),
                       T("press F1", "pulsa F1"));
  } else {
    ImGui::TextUnformatted(T("Fractured Space Offline  -  F1: menu", "Fractured Space Offline  -  F1: menú"));
  }
  ImGui::End();
}

// ---------------------------------------------------------------- hooks

static bool IsInputMsg(UINT m) {
  return (m >= WM_KEYFIRST && m <= WM_KEYLAST) || (m >= WM_MOUSEFIRST && m <= WM_MOUSELAST) || m == WM_INPUT ||
         m == WM_SETCURSOR;
}

static LRESULT CALLBACK HookWndProc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
  if (m == WM_KEYDOWN && wp == VK_F1) {
    if (!(lp & (1 << 30))) { // not auto-repeat
      g_open = !g_open;
      if (g_open) {
        g_lastRefresh = 0;
        g_startTick = 0; // hide the hint once the menu was used
      }
    }
    return 0;
  }
  if (m == WM_KEYUP && wp == VK_F1)
    return 0;
  if (g_open && g_ready) {
    ImGui_ImplWin32_WndProcHandler(h, m, wp, lp);
    if (IsInputMsg(m)) {
      if (m == WM_SETCURSOR) {
        SetCursor(NULL);
        return TRUE;
      }
      return 0; // the game does not see input while the menu is open
    }
  }
  return CallWindowProcW(g_oWndProc, h, m, wp, lp);
}

static void CreateRTV(IDXGISwapChain *sc) {
  ID3D11Texture2D *back = NULL;
  if (SUCCEEDED(sc->GetBuffer(0, __uuidof(ID3D11Texture2D), (void **)&back)) && back) {
    g_device->CreateRenderTargetView(back, NULL, &g_rtv);
    back->Release();
  }
}

static void InitImGui(IDXGISwapChain *sc) {
  if (FAILED(sc->GetDevice(__uuidof(ID3D11Device), (void **)&g_device)))
    return;
  g_device->GetImmediateContext(&g_context);
  DXGI_SWAP_CHAIN_DESC d;
  sc->GetDesc(&d);
  g_window = d.OutputWindow;
  CreateRTV(sc);

  ImGui::CreateContext();
  ImGuiIO &io = ImGui::GetIO();
  io.IniFilename = NULL;
  io.ConfigFlags |= ImGuiConfigFlags_NoMouseCursorChange;
  RECT rc;
  GetClientRect(g_window, &rc);
  float scale = (rc.bottom - rc.top) / 1080.0f;
  if (scale < 1)
    scale = 1;
  char font[MAX_PATH];
  GetWindowsDirectoryA(font, MAX_PATH);
  strcat_s(font, "\\Fonts\\segoeui.ttf");
  if (GetFileAttributesA(font) != INVALID_FILE_ATTRIBUTES)
    io.Fonts->AddFontFromFileTTF(font, 19.0f * scale, NULL, io.Fonts->GetGlyphRangesDefault());
  else {
    ImFontConfig cfg;
    cfg.SizePixels = 13.0f * scale;
    io.Fonts->AddFontDefault(&cfg);
  }
  ApplyStyle(scale);
  ImGui_ImplWin32_Init(g_window);
  ImGui_ImplDX11_Init(g_device, g_context);
  g_oWndProc = (WNDPROC)SetWindowLongPtrW(g_window, GWLP_WNDPROC, (LONG_PTR)HookWndProc);
  g_ready = true;
  MenuLog("menu: ImGui ready on window %p (%ldx%ld)", (void *)g_window, rc.right - rc.left, rc.bottom - rc.top);
}

static HRESULT __stdcall HookPresent(IDXGISwapChain *sc, UINT sync, UINT flags) {
  if (!g_ready)
    InitImGui(sc);
  if (g_ready) {
    if (!g_rtv)
      CreateRTV(sc);
    bool hint = GetTickCount() - g_startTick <= 25000 || g_hasRequests;
    if (g_rtv && (g_open || hint)) {
      ImGui::GetIO().MouseDrawCursor = g_open;
      ImGui_ImplDX11_NewFrame();
      ImGui_ImplWin32_NewFrame();
      ImGui::NewFrame();
      if (g_open)
        DrawMenu();
      DrawHint();
      ImGui::Render();
      g_context->OMSetRenderTargets(1, &g_rtv, NULL);
      ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
    }
  }
  return g_oPresent(sc, sync, flags);
}

static HRESULT __stdcall HookResizeBuffers(IDXGISwapChain *sc, UINT n, UINT w, UINT h, DXGI_FORMAT f, UINT fl) {
  if (g_rtv) {
    g_rtv->Release();
    g_rtv = NULL;
  }
  if (g_ready)
    ImGui_ImplDX11_InvalidateDeviceObjects();
  HRESULT hr = g_oResize(sc, n, w, h, f, fl);
  if (g_ready)
    ImGui_ImplDX11_CreateDeviceObjects();
  return hr;
}

static DWORD WINAPI Init(LPVOID) {
  wchar_t env[128];
  DWORD n = GetEnvironmentVariableW(L"FSO_OFFLINE_MENU", env, 128);
  if (n == 0 || n >= 128)
    return 0;
  std::wstring v(env);
  size_t colon = v.find(L':');
  if (colon == std::wstring::npos)
    return 0;
  g_port = _wtoi(v.substr(0, colon).c_str());
  g_token = v.substr(colon + 1);
  g_es = PRIMARYLANGID(GetUserDefaultUILanguage()) == LANG_SPANISH;

  // The game creates its device after start-up; kiero needs d3d11 loaded.
  for (int i = 0; i < 600 && !GetModuleHandleW(L"d3d11.dll"); ++i)
    Sleep(100);
  // This kiero copy does not initialise MinHook itself.
  int mh = MH_Initialize();
  if (mh != MH_OK && mh != MH_ERROR_ALREADY_INITIALIZED) {
    MenuLog("menu: MH_Initialize failed: %d", mh);
    return 0;
  }
  for (int i = 0; i < 100; ++i) {
    int st = kiero::init(kiero::RenderType::D3D11);
    if (st == kiero::Status::Success) {
      int a = kiero::bind(8, (void **)&g_oPresent, HookPresent);
      int b = kiero::bind(13, (void **)&g_oResize, HookResizeBuffers);
      g_startTick = GetTickCount();
      MenuLog("menu: DirectX 11 hooks installed (present %d, resize %d)", a, b);
      CreateThread(NULL, 0, PollRequests, NULL, 0, NULL);
      return 0;
    }
    if (i == 0 || i == 99)
      MenuLog("menu: kiero init attempt %d: status %d", i, st);
    Sleep(200);
  }
  return 0;
}

BOOL APIENTRY DllMain(HMODULE mod, DWORD reason, LPVOID) {
  if (reason == DLL_PROCESS_ATTACH) {
    DisableThreadLibraryCalls(mod);
    CreateThread(NULL, 0, Init, NULL, 0, NULL);
  }
  return TRUE;
}
