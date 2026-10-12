import QtQuick

// Plain TextEdit checks clipboard MIME formats without retrieving text in
// Qt 6.12. TextInput's automatic canPaste update retrieves the payload.
// Every user paste path here is intercepted before the native editor sees it.
FocusScope {
  id: root
  activeFocusOnTab: true

  property string text: ""
  property alias font: editor.font
  property alias color: editor.color
  property string placeholderText: ""
  property string accessibleName: "Objective"
  property bool pastePending: false
  property int pasteSerial: 0
  property var pasteSnapshot: null
  property bool changingText: false
  signal edited(string value)
  signal pasteRequested(bool primary, int serial)
  signal inputRejected(string message)

  function normalize(value) {
    return String(value).replace(/\r\n|[\r\n\t\u2028\u2029]/g, " ")
  }

  function acceptable(value) {
    return Array.from(value).length <= 480 && !/[\u0000-\u001f\u007f]/.test(value)
  }

  function requestPaste(primary) {
    if (!enabled || pastePending) return
    editor.forceActiveFocus()
    pasteSerial += 1
    pasteSnapshot = {
      text: editor.text, cursor: editor.cursorPosition,
      start: editor.selectionStart, end: editor.selectionEnd
    }
    pastePending = true
    pasteRequested(primary, pasteSerial)
  }

  function finishPaste(value, serial, error) {
    if (!pastePending || serial !== pasteSerial) return
    var snapshot = pasteSnapshot
    pastePending = false
    pasteSnapshot = null
    if (error !== "") { inputRejected(error); return }
    if (!enabled || !visible || !editor.activeFocus || !snapshot
        || editor.text !== snapshot.text || editor.cursorPosition !== snapshot.cursor
        || editor.selectionStart !== snapshot.start || editor.selectionEnd !== snapshot.end) return
    var inserted = normalize(value)
    var candidate = editor.text.slice(0, snapshot.start) + inserted + editor.text.slice(snapshot.end)
    if (!acceptable(candidate)) {
      inputRejected("Text can contain at most 480 characters and no control characters.")
      return
    }
    changingText = true
    // Replace the native selection as one undo block, without native paste.
    editor.textDocument.modified = false
    editor.cursorSelection.text = inserted
    editor.cursorPosition = snapshot.start + inserted.length
    editor.textDocument.modified = false
    changingText = false
    edited(editor.text)
  }

  function cancelPaste() {
    pastePending = false
    pasteSnapshot = null
    pasteSerial += 1
  }

  onTextChanged: {
    if (editor.text !== text) {
      changingText = true
      editor.text = text
      changingText = false
    }
  }
  onVisibleChanged: if (!visible) cancelPaste()
  onEnabledChanged: if (!enabled) cancelPaste()

  Flickable {
    id: viewport
    anchors.fill: parent
    contentWidth: Math.max(width, editor.contentWidth + 2)
    contentHeight: height
    interactive: false
    clip: true

    function revealCursor() {
      var rectangle = editor.cursorRectangle
      if (rectangle.x < contentX) contentX = rectangle.x
      else if (rectangle.x + rectangle.width > contentX + width)
        contentX = rectangle.x + rectangle.width - width
      contentX = Math.max(0, Math.min(contentX, contentWidth - width))
    }

    TextEdit {
      id: editor
      objectName: "limitless-objective-editor"
      width: viewport.contentWidth
      height: viewport.height
      text: root.text
      textFormat: TextEdit.PlainText
      wrapMode: TextEdit.NoWrap
      verticalAlignment: TextEdit.AlignVCenter
      clip: true
      activeFocusOnTab: false
      selectByMouse: true
      selectByKeyboard: true
      focus: true
      Accessible.name: root.accessibleName
      onCursorRectangleChanged: viewport.revealCursor()
      Keys.priority: Keys.BeforeItem
      Keys.onPressed: function(event) {
        if (event.matches(StandardKey.Paste)) {
          event.accepted = true
          root.requestPaste(false)
        } else {
          root.cancelPaste()
          if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
            event.accepted = true
          else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
            var next = root.nextItemInFocusChain(event.key === Qt.Key_Tab)
            if (next && next !== root) next.forceActiveFocus(
              event.key === Qt.Key_Tab ? Qt.TabFocusReason : Qt.BacktabFocusReason)
            event.accepted = true
          }
        }
      }
      onCursorPositionChanged: if (!root.changingText && root.pastePending) root.cancelPaste()
      onSelectionStartChanged: if (!root.changingText && root.pastePending) root.cancelPaste()
      onSelectionEndChanged: if (!root.changingText && root.pastePending) root.cancelPaste()
      onActiveFocusChanged: if (!activeFocus) root.cancelPaste()
      onTextChanged: {
        if (root.changingText) return
        if (root.pastePending) root.cancelPaste()
        var value = root.normalize(text)
        if (!root.acceptable(value)) {
          var position = cursorPosition
          root.changingText = true
          text = root.text
          cursorPosition = Math.min(position, text.length)
          root.changingText = false
          root.inputRejected("Text can contain at most 480 characters and no control characters.")
          return
        }
        if (value !== text) {
          root.changingText = true
          text = value
          root.changingText = false
        }
        root.edited(value)
      }

      // Qt otherwise reads the primary selection on a middle-button release.
      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.MiddleButton
        onPressed: function(mouse) {
          mouse.accepted = true
          editor.forceActiveFocus()
          editor.cursorPosition = editor.positionAt(mouse.x, mouse.y)
          root.requestPaste(true)
        }
        onReleased: function(mouse) { mouse.accepted = true }
      }

      Text {
        textFormat: Text.PlainText
        anchors.fill: parent
        verticalAlignment: Text.AlignVCenter
        visible: editor.text === "" && !editor.inputMethodComposing
        text: root.placeholderText
        color: editor.color
        opacity: 0.45
        font: editor.font
      }
    }
  }
}
