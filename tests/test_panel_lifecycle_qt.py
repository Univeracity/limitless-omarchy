"""Exercise production deferred callbacks across real QML object destruction."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")
pytest.importorskip("PySide6", reason="Run the dedicated Qt job for this gate.")
from PySide6.QtCore import QMetaObject, QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from shiboken6 import delete

ROOT = Path(__file__).parents[1]


def deferred_callbacks():
    for name in ("Panel.qml", "PanelContents.qml"):
        source = (ROOT / "plugin" / name).read_text(encoding="utf-8")
        callbacks = re.findall(r"Qt\.callLater\(function\(\) \{[^\n]+\}\)", source)
        assert len(callbacks) == source.count("Qt.callLater("), "Extend the harness for new callback shapes."
        for index, callback in enumerate(callbacks):
            yield pytest.param(callback, id=f"{name}-{index}")


@pytest.fixture(scope="session")
def app():
    return QGuiApplication.instance() or QGuiApplication([])


def run_callback(app, tmp_path, callback, *, destroyed=False, opened=True, runtime_ready=True):
    view = QQuickView()
    warnings = []
    view.engine().warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    source = tmp_path / "deferred-panel-test.qml"
    source.write_text(
        """import QtQuick
Item {
    id: host
    property int actions: 0
    Component {
        id: panelComponent
        Item {
            id: root
            objectName: "panel"
            property bool opened: true
            property bool runtimeReady: true
            function refresh() { host.actions++ }
            function inspectService() { host.actions++ }
            function refreshDrafts() { host.actions++ }
            signal enqueue()
            onEnqueue: { CALLBACK }
            QtObject {
                id: keyCatcher
                function forceActiveFocus() { host.actions++ }
            }
            QtObject {
                id: panelFlick
                property real contentY: 30
                onContentYChanged: host.actions++
            }
        }
    }
    Component.onCompleted: panelComponent.createObject(host)
}
""".replace("CALLBACK", callback),
        encoding="utf-8",
    )
    view.setSource(QUrl.fromLocalFile(str(source)))
    assert not view.errors(), [error.toString() for error in view.errors()]
    host = view.rootObject()
    assert host is not None
    try:
        panel = host.findChild(QObject, "panel")
        assert panel is not None
        panel.setProperty("opened", opened)
        panel.setProperty("runtimeReady", runtime_ready)
        assert QMetaObject.invokeMethod(panel, "enqueue")
        if destroyed:
            delete(panel)
        app.processEvents()
        return host.property("actions"), warnings
    finally:
        view.setSource(QUrl())
        app.processEvents()


@pytest.mark.parametrize("callback", list(deferred_callbacks()))
def test_live_panel_still_runs_queued_work(app, tmp_path, callback):
    actions, warnings = run_callback(app, tmp_path, callback)
    assert actions == 1
    assert warnings == []


@pytest.mark.parametrize("callback", list(deferred_callbacks()))
def test_destroyed_panel_does_not_run_or_raise_from_queued_work(app, tmp_path, callback):
    actions, warnings = run_callback(app, tmp_path, callback, destroyed=True)
    assert actions == 0
    assert warnings == []


def test_unguarded_callback_control_reproduces_the_reported_null_root_error(app, tmp_path):
    actions, warnings = run_callback(app, tmp_path, "Qt.callLater(function() { root.refresh() })", destroyed=True)
    assert actions == 0
    assert any("Cannot call method 'refresh' of null" in warning for warning in warnings), warnings


@pytest.mark.parametrize("callback", [p for p in deferred_callbacks() if "root.opened" in p.values[0]])
def test_closed_panel_does_not_run_follow_up_work(app, tmp_path, callback):
    actions, warnings = run_callback(app, tmp_path, callback, opened=False)
    assert actions == 0
    assert warnings == []


@pytest.mark.parametrize("callback", [p for p in deferred_callbacks() if "root.runtimeReady" in p.values[0]])
def test_unready_runtime_does_not_refresh_drafts(app, tmp_path, callback):
    actions, warnings = run_callback(app, tmp_path, callback, runtime_ready=False)
    assert actions == 0
    assert warnings == []
