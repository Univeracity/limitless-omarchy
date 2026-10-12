"""Executable clipboard and editing regression checks against real Qt Quick."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")
pytest.importorskip("PySide6", reason="Run the dedicated Qt clipboard-input job for this gate.")
from PySide6.QtCore import QCoreApplication, QMimeData, QObject, QPoint, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QInputMethodEvent
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="session")
def app():
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def field(app):
    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.setSource(QUrl.fromLocalFile(str(ROOT / "plugin" / "ClipboardTextField.qml")))
    assert not view.errors(), [error.toString() for error in view.errors()]
    view.resize(340, 36)
    view.show()
    view.requestActivate()
    QTest.qWait(20)
    root = view.rootObject()
    root.edited.connect(lambda text: root.setProperty("text", text))
    editor = root.findChild(QObject, "limitless-objective-editor")
    assert editor is not None
    editor.forceActiveFocus()
    yield view, root, editor
    view.close()
    view.setSource(QUrl())
    app.processEvents()


class LazyText(QMimeData):
    """A selection advertising text; count only actual payload retrieval."""

    def __init__(self):
        super().__init__()
        self.reads = 0

    def formats(self):
        return ["text/plain"]

    def retrieveData(self, mime_type, preferred_type):
        self.reads += 1
        return "foreign-selection-sentinel"


def test_clipboard_changes_do_not_fetch_payload_but_legacy_textinput_does(app, field, tmp_path):
    _, root, _ = field
    offered = LazyText()
    app.clipboard().setMimeData(offered)
    app.processEvents()
    assert offered.reads == 0
    assert root.property("text") == ""

    legacy = tmp_path / "legacy.qml"
    legacy.write_text("import QtQuick\nTextInput { width: 340; height: 36 }")
    control = QQuickView()
    control.setSource(QUrl.fromLocalFile(str(legacy)))
    assert not control.errors()
    positive_control = LazyText()
    app.clipboard().setMimeData(positive_control)
    app.processEvents()
    assert positive_control.reads > 0
    control.setSource(QUrl())
    app.clipboard().clear()


def test_typing_selection_unicode_ime_and_clear_remain_native(app, field):
    view, root, editor = field
    for char in "search this repo":
        QTest.keyClick(view, Qt.Key(ord(char.upper())))
    assert root.property("text") == "search this repo"
    editor.selectAll()
    event = QInputMethodEvent()
    event.setCommitString("café 😀")
    QCoreApplication.sendEvent(editor, event)
    assert root.property("text") == "café 😀"
    root.setProperty("text", "")
    assert editor.property("text") == ""


@pytest.mark.parametrize("key,modifier", [(Qt.Key_V, Qt.ControlModifier), (Qt.Key_Insert, Qt.ShiftModifier)])
def test_keyboard_paste_is_intercepted_and_replaces_selection(field, key, modifier):
    view, root, editor = field
    root.setProperty("text", "old objective")
    editor.selectAll()
    requested = []
    root.pasteRequested.connect(lambda primary, serial: requested.append((primary, serial)))
    QTest.keyClick(view, key, modifier)
    assert len(requested) == 1 and requested[0][0] is False
    assert root.property("text") == "old objective"
    root.finishPaste("new objective", requested[0][1], "")
    assert root.property("text") == "new objective"


def test_middle_click_is_intercepted_for_primary_selection(field):
    view, root, _ = field
    requested = []
    root.pasteRequested.connect(lambda primary, serial: requested.append((primary, serial)))
    QTest.mouseClick(view, Qt.MiddleButton, Qt.NoModifier, QPoint(10, 15))
    assert len(requested) == 1 and requested[0][0] is True


def test_bounded_selection_paste_is_one_native_undo_block(field):
    view, root, editor = field
    root.setProperty("text", "old objective")
    editor.selectAll()
    root.requestPaste(False)
    root.finishPaste("new objective", root.property("pasteSerial"), "")
    assert root.property("text") == "new objective"
    QTest.keyClick(view, Qt.Key_Z, Qt.ControlModifier)
    assert root.property("text") == "old objective"
    QTest.keyClick(view, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
    assert root.property("text") == "new objective"


def test_navigation_and_focus_loss_invalidate_a_pending_paste_even_if_restored(field):
    _, root, editor = field
    root.setProperty("text", "keep")
    editor.setProperty("cursorPosition", 0)
    root.requestPaste(False)
    serial = root.property("pasteSerial")
    editor.setProperty("cursorPosition", 1)
    editor.setProperty("cursorPosition", 0)
    root.finishPaste("late", serial, "")
    assert root.property("text") == "keep"
    root.requestPaste(False)
    serial = root.property("pasteSerial")
    editor.setProperty("focus", False)
    editor.forceActiveFocus()
    root.finishPaste("late", serial, "")
    assert root.property("text") == "keep"


def test_failed_oversized_and_stale_pastes_leave_the_objective_unchanged(field):
    _, root, editor = field
    root.setProperty("text", "keep")
    root.requestPaste(False)
    root.finishPaste("", root.property("pasteSerial"), "Clipboard did not finish within two seconds.")
    assert root.property("text") == "keep"
    root.requestPaste(False)
    root.finishPaste("x" * 481, root.property("pasteSerial"), "")
    assert root.property("text") == "keep"
    root.requestPaste(False)
    serial = root.property("pasteSerial")
    editor.setProperty("cursorPosition", len("keep"))
    root.finishPaste("late", serial, "")
    assert root.property("text") == "keep"
    root.requestPaste(False)
    serial = root.property("pasteSerial")
    root.cancelPaste()
    root.finishPaste("late", serial, "")
    assert root.property("text") == "keep"


def test_character_limit_and_plain_text_rendering(field):
    view, root, editor = field
    root.setProperty("text", "x" * 480)
    editor.setProperty("cursorPosition", 480)
    QTest.keyClick(view, Qt.Key_Y)
    assert root.property("text") == "x" * 480
    root.setProperty("text", "")
    root.requestPaste(False)
    root.finishPaste("<b>plain</b>\nsecond", root.property("pasteSerial"), "")
    assert root.property("text") == "<b>plain</b> second"


def test_tab_leaves_the_single_line_editor_without_inserting_text(app, tmp_path):
    source = tmp_path / "focus.qml"
    source.write_text(
        'import QtQuick\nimport "' + (ROOT / "plugin").as_uri() + '" as Plugin\n'
        "Rectangle { width: 440; height: 100; "
        'Plugin.ClipboardTextField { id: first; objectName: "first-field"; width: 340; height: 36; '
        "activeFocusOnTab: true; onEdited: function(value) { text = value } } "
        'Rectangle { objectName: "next-control"; y: 50; width: 100; height: 36; activeFocusOnTab: true } }'
    )
    view = QQuickView()
    try:
        view.setSource(QUrl.fromLocalFile(str(source)))
        assert not view.errors(), [error.toString() for error in view.errors()]
        view.show()
        view.requestActivate()
        first = view.rootObject().findChild(QObject, "first-field")
        editor = first.findChild(QObject, "limitless-objective-editor")
        editor.forceActiveFocus()
        QTest.qWait(20)
        QTest.keyClick(view, Qt.Key_Tab)
        assert first.property("text") == ""
        assert view.rootObject().findChild(QObject, "next-control").property("activeFocus")
        QTest.keyClick(view, Qt.Key_Tab, Qt.ShiftModifier)
        assert editor.property("activeFocus")
    finally:
        view.close()
        view.setSource(QUrl())
        app.processEvents()
