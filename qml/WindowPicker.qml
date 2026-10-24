import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

AppDialog {
    id: dialog
    objectName: "windowPicker"
    title: rift.pickerName ? "Select windows for new group" : "Select windows to add"
    preferredWidth: Kirigami.Units.gridUnit * 34
    onOpened: {
        search.text = ""
        search.forceActiveFocus()
    }
    onRejected: rift.cancelPicker()

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.largeSpacing
        Controls.Label {
            text: rift.pickerName
                ? "Choose windows for “" + rift.pickerName + "”. The group is created only when you confirm."
                : "Choose from this snapshot of open main windows. Already-saved windows are skipped; existing entries stay unchanged."
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
        Controls.TextField {
            id: search
            objectName: "windowSearch"
            placeholderText: "Search window titles or apps…"
            Accessible.name: "Search windows"
            selectByMouse: true
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
        Controls.ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 16
            Layout.minimumHeight: Kirigami.Units.gridUnit * 3
            contentWidth: availableWidth
            ListView {
                id: candidates
                objectName: "candidateList"
                clip: true
                model: {
                    const query = search.text.trim().toLowerCase()
                    return rift.candidates.filter(w => (w.title + " " + w.app_name + " " + w.app_id).toLowerCase().includes(query))
                }
                delegate: Controls.CheckDelegate {
                    required property var modelData
                    objectName: "candidate_" + modelData.candidate_index
                    width: ListView.view.width
                    checked: rift.pickedIndices.includes(modelData.candidate_index)
                    Accessible.name: (modelData.title || "Untitled window") + " — " + modelData.app_name
                    onToggled: rift.setPicked(modelData.candidate_index, checked)
                    contentItem: ColumnLayout {
                        Controls.Label {
                            text: modelData.title || "Untitled window"
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                        }
                        Controls.Label {
                            text: modelData.app_name + " · " + modelData.w + " × " + modelData.h + " · " + modelData.x + ", " + modelData.y
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            color: Kirigami.Theme.disabledTextColor
                        }
                    }
                    Controls.ToolTip.visible: hovered
                    Controls.ToolTip.text: Accessible.name
                }
                Controls.Label {
                    anchors.centerIn: parent
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    visible: candidates.count === 0
                    text: rift.candidates.length === 0 ? "No main windows found." : "No matching windows."
                }
            }
        }
        Controls.Label {
            objectName: "pickedCount"
            text: rift.pickedCount + " selected (including selections hidden by search)"
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
    }
    footer: Controls.DialogButtonBox {
        Controls.Button {
            objectName: "addPickedButton"
            text: rift.pickerName ? "Create group" : "Add selected"
            highlighted: true
            enabled: !rift.busy && rift.pickedCount > 0
            onClicked: {
                if (rift.addPicked()) dialog.close()
            }
        }
        Controls.Button {
            text: "Cancel"
            Controls.DialogButtonBox.buttonRole: Controls.DialogButtonBox.RejectRole
        }
    }
}
