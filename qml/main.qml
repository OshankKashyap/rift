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
    property int removeId: 0
    property string removeTitle
    pageStack.objectName: "groupPages"
    pageStack.defaultColumnWidth: Kirigami.Units.gridUnit * 15

    function openGroup(groupId: int): void {
        if (rift.selected !== groupId) rift.select(groupId)
        if (root.pageStack.depth === 1) {
            root.pageStack.push(detailPage.createObject(root.pageStack))
        }
    }
    function startCapture(): void {
        captureDialog.text = ""
        captureDialog.selectWindows = false
        captureDialog.open()
    }
    function editEntry(entry): void {
        overrideDialog.windowId = entry.id
        desktopFile.text = entry.desktop_file
        matchApp.text = entry.match_app_id
        matchTitle.text = entry.match_title
        matchProcess.text = entry.match_process
        overrideDialog.open()
    }
    Connections {
        target: rift
        function onPickerReady() { windowPicker.open() }
        function onChanged() {
            if (rift.selected > 0 && root.pageStack.depth === 1) root.openGroup(rift.selected)
        }
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

    footer: Controls.Pane {
        padding: Kirigami.Units.largeSpacing
        contentItem: RowLayout {
            spacing: Kirigami.Units.largeSpacing
            Controls.BusyIndicator {
                running: rift.busy
                visible: running
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: implicitWidth
                Accessible.name: "Operation in progress"
            }
            Kirigami.Icon {
                source: "dialog-information"
                visible: !rift.busy
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: implicitWidth
            }
            Controls.ScrollView {
                id: statusView
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(statusText.implicitHeight, Kirigami.Units.gridUnit * 4)
                contentWidth: availableWidth
                clip: true
                Controls.TextArea {
                    id: statusText
                    objectName: "statusText"
                    width: statusView.availableWidth
                    text: rift.status
                    readOnly: true
                    selectByMouse: true
                    wrapMode: Text.Wrap
                    textFormat: Text.PlainText
                    padding: 0
                    background: null
                    Accessible.name: "Operation status"
                }
            }
        }
    }

    pageStack.initialPage: Kirigami.ScrollablePage {
        title: "Window groups"
        header: Controls.Pane {
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                Controls.Label {
                    text: "Save a workspace. Bring it back when you need it."
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    color: Kirigami.Theme.disabledTextColor
                }
                Controls.Button {
                    objectName: "captureWindowsButton"
                    text: "Capture windows…"
                    icon.name: "list-add"
                    Layout.fillWidth: true
                    enabled: !rift.busy
                    onClicked: root.startCapture()
                }
            }
        }
        ListView {
            id: groupList
            objectName: "groupList"
            model: rift.groups
            spacing: Kirigami.Units.smallSpacing
            delegate: Controls.ItemDelegate {
                required property var modelData
                required property int index
                width: ListView.view.width
                enabled: !rift.busy
                highlighted: modelData.id === rift.selected
                Accessible.name: modelData.name
                onClicked: {
                    groupList.currentIndex = index
                    root.openGroup(modelData.id)
                }
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon {
                        source: "view-grid"
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: implicitWidth
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: Kirigami.Units.smallSpacing
                        Controls.Label {
                            text: modelData.name
                            textFormat: Text.PlainText
                            font.bold: modelData.id === rift.selected
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                        Controls.Label {
                            text: "Saved " + modelData.created_at.split(" ")[0]
                            font: Kirigami.Theme.smallFont
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                    }
                }
                Controls.ToolTip.visible: hovered
                Controls.ToolTip.text: modelData.name
            }
            Kirigami.PlaceholderMessage {
                objectName: "groupPlaceholder"
                parent: groupList
                anchors.centerIn: parent
                visible: groupList.count === 0
                text: "No groups yet"
                explanation: "Open the apps you need, then capture your windows."
                icon.name: "view-grid"
                width: Math.min(parent.width, Kirigami.Units.gridUnit * 24)
            }
        }
    }

    Component {
        id: detailPage
        Kirigami.ScrollablePage {
            objectName: "groupDetail"
            Layout.fillWidth: true
            title: rift.groupName
            header: Controls.Pane {
                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Controls.Label {
                        text: rift.windows.length + " captured window entries · Already-running apps are skipped."
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        color: Kirigami.Theme.disabledTextColor
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Controls.Button {
                            objectName: "launchGroupButton"
                            text: "Launch group"
                            icon.name: "media-playback-start"
                            highlighted: true
                            enabled: !rift.busy && rift.windows.length > 0
                            onClicked: rift.launch(rift.selected)
                        }
                        Controls.Button {
                            text: "Recall…"
                            icon.name: "window-close"
                            enabled: !rift.busy && rift.windows.length > 0
                            onClicked: { root.recallId = rift.selected; recallDialog.open() }
                            Controls.ToolTip.visible: hovered
                            Controls.ToolTip.text: "Close all running windows of this group's apps"
                        }
                        Controls.Button {
                            text: "Add windows"
                            icon.name: "list-add"
                            enabled: !rift.busy
                            onClicked: rift.capture("", rift.selected)
                        }
                        Controls.Button {
                            objectName: "selectWindowsButton"
                            text: "Select windows…"
                            icon.name: "edit-select"
                            enabled: !rift.busy
                            onClicked: rift.preparePicker(rift.selected)
                        }
                        Controls.ToolButton {
                            text: "More"
                            icon.name: "overflow-menu"
                            enabled: !rift.busy
                            onClicked: groupMenu.popup()
                            Controls.Menu {
                                id: groupMenu
                                Controls.MenuItem {
                                    text: "Rename group…"
                                    icon.name: "edit-rename"
                                    onTriggered: { renameDialog.text = rift.groupName; renameDialog.open() }
                                }
                                Controls.MenuSeparator {}
                                Controls.MenuItem {
                                    text: "Delete group…"
                                    icon.name: "edit-delete"
                                    onTriggered: deleteDialog.open()
                                }
                            }
                        }
                    }
                }
            }
            ListView {
                id: windowList
                objectName: "windowList"
                model: rift.windows
                spacing: Kirigami.Units.largeSpacing
                leftMargin: Kirigami.Units.largeSpacing
                rightMargin: Kirigami.Units.largeSpacing
                topMargin: Kirigami.Units.smallSpacing
                bottomMargin: Kirigami.Units.largeSpacing
                delegate: Kirigami.AbstractCard {
                    required property var modelData
                    objectName: "windowCard"
                    enabled: !rift.busy
                    focusPolicy: Qt.NoFocus
                    contentItem: RowLayout {
                        spacing: Kirigami.Units.largeSpacing
                        Kirigami.Icon {
                            source: modelData.app_id.replace(/\.desktop$/i, "") || "application-x-executable"
                            fallback: "application-x-executable"
                            implicitWidth: Kirigami.Units.iconSizes.medium
                            implicitHeight: implicitWidth
                            Layout.alignment: Qt.AlignTop
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Kirigami.Units.smallSpacing
                            Controls.Label {
                                text: modelData.title || "Untitled window"
                                font.bold: true
                                textFormat: Text.PlainText
                                wrapMode: Text.Wrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                            }
                            Controls.Label {
                                text: modelData.app_id || "App ID missing — review matching"
                                textFormat: Text.PlainText
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                color: Kirigami.Theme.disabledTextColor
                            }
                            Controls.Label {
                                text: modelData.w + " × " + modelData.h + "  ·  Position " + modelData.x + ", " + modelData.y
                                font: Kirigami.Theme.smallFont
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                            Controls.Label {
                                visible: !modelData.desktop_file
                                text: "No saved launcher — review the launch target."
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                color: Kirigami.Theme.neutralTextColor
                            }
                        }
                        Controls.ToolButton {
                            icon.name: "document-edit"
                            Accessible.name: "Edit launch target and matching"
                            Controls.ToolTip.visible: hovered
                            Controls.ToolTip.text: "Edit launch target and matching"
                            onClicked: root.editEntry(modelData)
                        }
                        Controls.ToolButton {
                            icon.name: "list-remove"
                            Accessible.name: "Remove captured window"
                            Controls.ToolTip.visible: hovered
                            Controls.ToolTip.text: "Remove from group"
                            onClicked: {
                                root.removeId = modelData.id
                                root.removeTitle = modelData.title || "Untitled window"
                                removeDialog.open()
                            }
                        }
                    }
                }
                Kirigami.PlaceholderMessage {
                    objectName: "emptyGroupPlaceholder"
                    parent: windowList
                    anchors.centerIn: parent
                    visible: windowList.count === 0
                    width: windowList.width - windowList.leftMargin - windowList.rightMargin
                    text: "This group is empty"
                    explanation: "Use Add windows to capture the main windows currently open."
                    icon.name: "window-new"
                }
            }
        }
    }

    WindowPicker { id: windowPicker }

    NameDialog {
        id: captureDialog
        objectName: "captureDialog"
        title: "Capture windows"
        description: "Create a group from all open main windows, or choose specific windows. Helper dialogs and Rift itself are excluded."
        offerWindowSelection: true
        acceptText: selectWindows ? "Select windows…" : "Capture all"
        onSubmitted: function(name) {
            if (selectWindows) rift.preparePicker(0, name)
            else rift.capture(name, 0)
        }
    }
    NameDialog {
        id: renameDialog
        objectName: "renameDialog"
        title: "Rename group"
        description: "Choose a name that helps you recognize this workspace."
        onSubmitted: function(name) { rift.rename(name) }
    }
    AppDialog {
        id: deleteDialog
        objectName: "deleteDialog"
        title: "Delete this group?"
        confirmationText: "Delete group"
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.No
        contentItem: Controls.Label {
            text: "The group and its saved window entries will be permanently removed. Running apps will stay open."
            wrapMode: Text.Wrap
        }
        onAccepted: {
            rift.deleteGroup()
            if (rift.selected === 0 && root.pageStack.depth > 1) root.pageStack.pop()
        }
    }
    AppDialog {
        id: recallDialog
        objectName: "recallDialog"
        title: "Close this group's apps?"
        confirmationText: "Close matching windows"
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.No
        contentItem: ColumnLayout {
            spacing: Kirigami.Units.largeSpacing
            Kirigami.InlineMessage {
                objectName: "recallWarning"
                Layout.fillWidth: true
                type: Kirigami.MessageType.Warning
                visible: true
                text: "Recall closes ALL running windows of matching apps, including windows not captured in this group."
            }
            Controls.Label {
                text: "Apps may ask you to save your work. Rift never forces them to quit."
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }
        onAccepted: rift.recall(root.recallId)
    }
    AppDialog {
        id: removeDialog
        objectName: "removeDialog"
        title: "Remove captured window?"
        confirmationText: "Remove entry"
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.No
        contentItem: ColumnLayout {
            spacing: Kirigami.Units.largeSpacing
            Controls.Label {
                text: "Remove this saved entry from the group? The running window will stay open."
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Controls.Label {
                text: root.removeTitle
                textFormat: Text.PlainText
                font.bold: true
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
                Layout.fillWidth: true
                Layout.minimumWidth: 0
            }
        }
        onAccepted: rift.removeWindow(root.removeId)
    }
    AppDialog {
        id: overrideDialog
        objectName: "overrideDialog"
        property int windowId: 0
        title: "Launch target and matching"
        preferredWidth: Kirigami.Units.gridUnit * 34
        property bool validProcess: matchProcess.text.trim().length === 0 || matchProcess.text.trim().startsWith("/")
        contentItem: Controls.ScrollView {
            id: editorScroll
            objectName: "editorScroll"
            padding: Kirigami.Units.largeSpacing * 2
            implicitHeight: editorLayout.implicitHeight + topPadding + bottomPadding
            contentWidth: availableWidth
            clip: true
            ColumnLayout {
                id: editorLayout
                width: editorScroll.availableWidth
                spacing: Kirigami.Units.largeSpacing
                Controls.Label {
                    text: "The desktop entry tells Rift how to launch this app. Leave matching overrides blank to use its captured identity."
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                }
                Controls.Label { text: "Desktop file or desktop ID" }
                Controls.TextField {
                    id: desktopFile
                    objectName: "desktopFile"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    placeholderText: "org.kde.konsole or /path/to/app.desktop"
                    Accessible.name: "Desktop file or desktop ID"
                    selectByMouse: true
                }
                Kirigami.Separator { Layout.fillWidth: true }
                Kirigami.Heading { text: "Exact matching overrides"; level: 3 }
                Controls.Label {
                    text: "When provided, every nonblank override must match. Titles and process paths are case-sensitive."
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                }
                Controls.Label { text: "App ID" }
                Controls.TextField { id: matchApp; objectName: "matchApp"; Layout.fillWidth: true; Layout.minimumWidth: 0; Accessible.name: "Match app ID"; selectByMouse: true }
                Controls.Label { text: "Exact window title" }
                Controls.TextField { id: matchTitle; objectName: "matchTitle"; Layout.fillWidth: true; Layout.minimumWidth: 0; Accessible.name: "Match exact window title"; selectByMouse: true }
                Controls.Label { text: "Process executable (absolute path)" }
                Controls.TextField { id: matchProcess; objectName: "matchProcess"; Layout.fillWidth: true; Layout.minimumWidth: 0; Accessible.name: "Match process executable"; selectByMouse: true }
                Controls.Label {
                    visible: !overrideDialog.validProcess
                    text: "Use an absolute path beginning with /, or leave this blank."
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.neutralTextColor
                }
            }
        }
        footer: Controls.DialogButtonBox {
            Controls.Button {
                objectName: "matchingSaveButton"
                text: "Save"
                highlighted: true
                enabled: overrideDialog.validProcess
                Controls.DialogButtonBox.buttonRole: Controls.DialogButtonBox.AcceptRole
            }
            Controls.Button { text: "Cancel"; Controls.DialogButtonBox.buttonRole: Controls.DialogButtonBox.RejectRole }
        }
        onOpened: desktopFile.forceActiveFocus()
        onAccepted: {
            if (validProcess) rift.updateWindow(windowId, desktopFile.text.trim(), matchApp.text.trim(), matchTitle.text.trim(), matchProcess.text.trim())
        }
    }
}
