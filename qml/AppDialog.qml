import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Controls.Dialog {
    id: dialog
    property real preferredWidth: Kirigami.Units.gridUnit * 28
    property string confirmationText
    parent: Controls.Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(preferredWidth, parent.width - Kirigami.Units.largeSpacing * 4)
    height: Math.min(implicitHeight, parent.height - Kirigami.Units.largeSpacing * 4)
    modal: true
    closePolicy: Controls.Popup.CloseOnEscape
    onOpened: {
        if (confirmationText.length > 0) {
            standardButton(Controls.Dialog.Yes).text = confirmationText
            const cancel = standardButton(Controls.Dialog.No)
            cancel.text = "Cancel"
            cancel.forceActiveFocus()
        }
    }
}
