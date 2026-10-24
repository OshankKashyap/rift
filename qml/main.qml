import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    width: 940
    height: 680
    minimumWidth: 640
    minimumHeight: 460
    visible: true
    title: "Rift"
    property bool trayAvailable: false
    property int recallId: 0
    function openGroup(groupId: int): void {
        rift.select(groupId)
        root.pageStack.push(detailPage.createObject(root.pageStack))
    }
    pageStack.onPageRemoved: function(page) {
        if (page.objectName === "groupDetail") page.destroy()
    }
    onClosing: function(close) {
        if (trayAvailable) {
            close.accepted = false
            hide()
        }
    }

    footer: Controls.ToolBar {
        RowLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            Controls.BusyIndicator { running: rift.busy; visible: running }
            Controls.Label {
                text: rift.status
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                textFormat: Text.PlainText
            }
        }
    }

    pageStack.initialPage: Kirigami.ScrollablePage {
        title: "Window groups"
        actions: [Kirigami.Action {
            text: "Capture current windows"
            icon.name: "list-add"
            enabled: !rift.busy
            onTriggered: { captureName.text = ""; captureDialog.open() }
        }]
        ListView {
            model: rift.groups
            spacing: Kirigami.Units.smallSpacing
            delegate: Controls.ItemDelegate {
                required property var modelData
                width: ListView.view.width
                enabled: !rift.busy
                onClicked: root.openGroup(modelData.id)
                contentItem: RowLayout {
                    Controls.Label {
                        text: modelData.name
                        textFormat: Text.PlainText
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    Controls.Button { text: "Open"; onClicked: root.openGroup(modelData.id) }
                    Controls.Button { text: "Launch"; onClicked: rift.launch(modelData.id) }
                    Controls.Button { text: "Recall…"; onClicked: { root.recallId = modelData.id; recallDialog.open() } }
                }
            }
            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                visible: parent.count === 0
                text: "No groups yet"
                explanation: "Capture your current main windows to get started."
            }
        }
    }

    Component {
        id: detailPage
        Kirigami.ScrollablePage {
            objectName: "groupDetail"
            title: rift.groupName
            actions: [
                Kirigami.Action { text: "Launch"; icon.name: "media-playback-start"; enabled: !rift.busy; onTriggered: rift.launch(rift.selected) },
                Kirigami.Action { text: "Recall…"; icon.name: "window-close"; enabled: !rift.busy; onTriggered: { root.recallId = rift.selected; recallDialog.open() } },
                Kirigami.Action { text: "Append current windows"; icon.name: "list-add"; enabled: !rift.busy; onTriggered: rift.capture("", rift.selected) },
                Kirigami.Action { text: "Rename…"; icon.name: "edit-rename"; enabled: !rift.busy; onTriggered: { renameName.text = rift.groupName; renameDialog.open() } },
                Kirigami.Action { text: "Delete…"; icon.name: "edit-delete"; enabled: !rift.busy; onTriggered: deleteDialog.open() }
            ]
            ListView {
                model: rift.windows
                spacing: Kirigami.Units.smallSpacing
                delegate: Controls.ItemDelegate {
                    required property var modelData
                    width: ListView.view.width
                    enabled: !rift.busy
                    contentItem: RowLayout {
                        ColumnLayout {
                            Layout.fillWidth: true
                            Controls.Label { text: modelData.title || "Untitled"; textFormat: Text.PlainText; elide: Text.ElideRight; Layout.fillWidth: true }
                            Controls.Label { text: "appId: " + (modelData.app_id || "missing — set an override"); textFormat: Text.PlainText; elide: Text.ElideRight; Layout.fillWidth: true }
                            Controls.Label { text: modelData.x + ", " + modelData.y + " · " + modelData.w + " × " + modelData.h }
                        }
                        Controls.Button {
                            text: "Edit matching…"
                            onClicked: {
                                overrideDialog.windowId = modelData.id
                                desktopFile.text = modelData.desktop_file
                                matchApp.text = modelData.match_app_id
                                matchTitle.text = modelData.match_title
                                matchProcess.text = modelData.match_process
                                overrideDialog.open()
                            }
                        }
                        Controls.Button { text: "Remove"; onClicked: rift.removeWindow(modelData.id) }
                    }
                }
            }
        }
    }

    Controls.Dialog {
        id: captureDialog
        objectName: "captureDialog"
        anchors.centerIn: parent
        title: "Capture current main windows"
        modal: true
        standardButtons: Controls.Dialog.Ok | Controls.Dialog.Cancel
        Controls.TextField { id: captureName; placeholderText: "Group name"; width: 320 }
        onAccepted: rift.capture(captureName.text, 0)
    }
    Controls.Dialog {
        id: renameDialog
        objectName: "renameDialog"
        anchors.centerIn: parent
        title: "Rename group"
        modal: true
        standardButtons: Controls.Dialog.Ok | Controls.Dialog.Cancel
        Controls.TextField { id: renameName; width: 320 }
        onAccepted: rift.rename(renameName.text)
    }
    Controls.Dialog {
        id: deleteDialog
        objectName: "deleteDialog"
        anchors.centerIn: parent
        title: "Delete this group?"
        modal: true
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.No
        Controls.Label { text: "Saved entries will be deleted. Running apps are not closed." }
        onAccepted: { rift.deleteGroup(); root.pageStack.pop() }
    }
    Controls.Dialog {
        id: recallDialog
        objectName: "recallDialog"
        anchors.centerIn: parent
        title: "Recall group?"
        modal: true
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.No
        Controls.Label { text: "Close all running windows matching this group's apps?\nApps may ask you to save unsaved work." }
        onAccepted: rift.recall(root.recallId)
    }
    Controls.Dialog {
        id: overrideDialog
        objectName: "overrideDialog"
        property int windowId: 0
        anchors.centerIn: parent
        title: "Launch target and exact matching overrides"
        modal: true
        width: Math.min(root.width - 40, 600)
        standardButtons: Controls.Dialog.Save | Controls.Dialog.Cancel
        contentItem: ColumnLayout {
            Controls.Label {
                text: "Blank overrides use captured identity. When provided, ALL override fields must match. Title is case-sensitive; appId is case-insensitive."
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Controls.Label { text: "Desktop file (absolute path or exact desktop ID)" }
            Controls.TextField { id: desktopFile; Layout.fillWidth: true }
            Controls.Label { text: "Match appId" }
            Controls.TextField { id: matchApp; Layout.fillWidth: true }
            Controls.Label { text: "Match exact window title" }
            Controls.TextField { id: matchTitle; Layout.fillWidth: true }
            Controls.Label { text: "Match process executable (absolute /proc/PID/exe target)" }
            Controls.TextField { id: matchProcess; Layout.fillWidth: true }
        }
        onAccepted: rift.updateWindow(windowId, desktopFile.text, matchApp.text, matchTitle.text, matchProcess.text)
    }
}
