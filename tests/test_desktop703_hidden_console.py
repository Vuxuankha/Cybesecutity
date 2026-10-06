from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT/rel).read_text(encoding="utf-8")

def test_background_network_processes_are_hidden_on_windows():
    platform=text("webapi/platform50.py")
    desktop=text("webapi/desktop70.py")
    discovery=text("webapi/autodiscovery5010.py")
    assert "hidden_subprocess_kwargs" in platform
    assert "WindowStyle','Hidden'" in platform
    assert "timeout=6,**hidden_subprocess_kwargs()" in platform
    assert 'timeout=5,**hidden_subprocess_kwargs())' in desktop
    assert "hidden_subprocess_kwargs" in discovery

def test_desktop_launcher_uses_hidden_vbs_and_pythonw():
    vbs=text("MO_APP_NETWORKAUTOMATION.vbs")
    alias=text("00_MO_APP_NETWORKAUTOMATION.vbs")
    core=text("_internal/launcher/START_DESKTOP_CORE.bat")
    assert "sh.Run(cmd, 0, True)" in vbs
    assert "wscript.exe" in alias.lower()
    assert "pythonw.exe" in core.lower()
    assert 'start "" /b' not in core.lower()
    assert "rmdir /s /q" not in core.lower()
    assert not (ROOT / "START_DESKTOP_7.bat").exists()

def test_pyinstaller_build_is_windowed():
    spec=text("NetworkAutomationDesktop.spec")
    assert "console=False" in spec
