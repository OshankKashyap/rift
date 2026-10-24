import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

AppDialog {
    id: dialog
    property alias text: nameField.text
    property string description
    property string acceptText: "Save"
    property bool offerWindowSelection: false
    property alias selectWindows: selectionChoice.checked
    signal submitted(string name)

    onOpened: {
        nameField.forceActiveFocus()
        nameField.selectAll()
    }
    onAccepted: {
        if (text.trim().length > 0) submitted(text.trim())
    }
    contentItem: ColumnLayout {
        spacing: Kirigami.Units.largeSpacing
        Controls.Label {
            text: dialog.description
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
        Controls.Label { text: "Group name" }
        Controls.TextField {
            id: nameField
            objectName: "nameField"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            placeholderText: "For example, Work or Study"
            Accessible.name: "Group name"
            selectByMouse: true
            onAccepted: {
                if (dialog.text.trim().length > 0) dialog.accept()
            }
        }
        Controls.Label {
            text: "Enter a name containing more than spaces."
            visible: nameField.text.length > 0 && nameField.text.trim().length === 0
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            color: Kirigami.Theme.neutralTextColor
        }
        Controls.CheckBox {
            id: selectionChoice
            objectName: "selectSpecificWindows"
            visible: dialog.offerWindowSelection
            text: "Select specific windows instead of capturing all"
            Layout.fillWidth: true
            contentItem: Controls.Label {
                text: selectionChoice.text
                wrapMode: Text.Wrap
                leftPadding: selectionChoice.indicator.width + selectionChoice.spacing
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
    footer: Controls.DialogButtonBox {
        Controls.Button {
            objectName: "nameAcceptButton"
            text: dialog.acceptText
            highlighted: true
            enabled: nameField.text.trim().length > 0
            Controls.DialogButtonBox.buttonRole: Controls.DialogButtonBox.AcceptRole
        }
        Controls.Button {
            text: "Cancel"
            Controls.DialogButtonBox.buttonRole: Controls.DialogButtonBox.RejectRole
        }
    }
}
