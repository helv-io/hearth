import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    width: 1440
    height: 900
    minimumWidth: 1100
    minimumHeight: 480
    visible: true
    color: "#09090B"
    title: "Hearth"

    property bool groupMode: false
    property string hot: ""
    property bool settingsOpen: false
    property bool fillingSettings: false
    property bool providerIsGrok: false
    property bool keyVisible: true
    property string providerHint: ""
    property string providerDocs: ""
    property bool confirmOpen: false

    function openSettings() {
        fillingSettings = true
        endpoint.text = controller.baseUrl
        modelBox.editText = controller.model
        keyField.text = ""
        forgetKey.checked = false
        updatesBox.checked = controller.checkUpdates
        for (let i = 0; i < providerBox.count; i++) {
            if (providerBox.valueAt(i) === controller.provider) {
                providerBox.currentIndex = i
                break
            }
        }
        applyPreset(providerBox.currentValue, false)
        fillingSettings = false
        settingsOpen = true
    }

    function presetById(id) {
        const rows = controller.providerPresets
        for (let i = 0; i < rows.length; i++) {
            if (rows[i].id === id)
                return rows[i]
        }
        return null
    }

    function applyPreset(id, fillEndpoint) {
        const preset = presetById(id) || {}
        providerIsGrok = !!preset.sso
        keyVisible = !!preset.needs_key || !!preset.optional || !!preset.sso
        providerHint = preset.hint || ""
        providerDocs = preset.docs || ""
        if (fillEndpoint && !preset.custom && preset.base)
            endpoint.text = preset.base
    }

    function hit(x, y) {
        const point = Qt.point(x, y)
        if (tray.blocks(point))
            return tray.targetAt(point)
        for (let i = 0; i < phones.count; i++) {
            const slot = phones.itemAt(i)
            const phone = slot ? slot.phone : null
            if (!phone)
                continue
            const target = phone.targetAt(point, groupMode)
            if (target)
                return target
        }
        return ""
    }

    QtObject {
        id: drag
        property bool active: false
        property real pointerX: 0
        property real pointerY: 0
        signal aborted()

        function begin(source, letter, ident, kind, x, y, sample, holdX, holdY) {
            ghost.letter = letter || ""
            ghost.ident = ident || ""
            ghost.kind = kind || "app"
            ghost.source = source
            ghost.sample = sample || null
            ghost.width = Math.max(1, sample && sample.width > 0 ? sample.width : 68)
            ghost.height = Math.max(1, sample && sample.height > 0 ? sample.height : 68)
            ghost.holdX = holdX
            ghost.holdY = holdY
            active = true
            place(x, y)
            ghost.visible = true
        }
        function move(x, y) { place(x, y) }
        function end(x, y) {
            if (!active)
                return
            const target = hit(x, y)
            const source = ghost.source
            cancel()
            if (source && target)
                controller.move(source, target)
        }
        function cancel() {
            const was = active || ghost.visible
            active = false
            ghost.visible = false
            ghost.sample = null
            ghost.source = ""
            win.hot = ""
            if (was)
                aborted()
        }
        function place(x, y) {
            pointerX = x
            pointerY = y
            const p = overlay.mapFromItem(null, x, y)
            ghost.x = p.x - ghost.holdX
            ghost.y = p.y - ghost.holdY
            win.hot = hit(x, y)
        }

        // Holding an icon against either page strip's side scrolls that strip.
        function flickUnderPointer() {
            if ((controller.folder.source || "") !== "" && tray.pagesFlick) {
                const folderLocal = tray.pagesFlick.mapFromItem(null, pointerX, pointerY)
                if (folderLocal.y >= 0 && folderLocal.y <= tray.pagesFlick.height
                        && folderLocal.x >= -36 && folderLocal.x <= tray.pagesFlick.width + 36)
                    return tray.pagesFlick
            }
            const stageLocal = stage.mapFromItem(null, pointerX, pointerY)
            if (stageLocal.y >= 0 && stageLocal.y <= stage.height
                    && stageLocal.x >= -36 && stageLocal.x <= stage.width + 36)
                return stage
            return null
        }

        function nudgePages() {
            if (!active)
                return
            const flick = flickUnderPointer()
            if (!flick || flick.width < 1)
                return
            const local = flick.mapFromItem(null, pointerX, pointerY)
            const margin = Math.min(72, Math.max(40, flick.width * 0.09))
            let dir = 0
            let depth = 0
            if (local.x < margin) {
                dir = -1
                depth = Math.max(0, Math.min(1, (margin - local.x) / margin))
            } else if (local.x > flick.width - margin) {
                dir = 1
                depth = Math.max(0, Math.min(1, (local.x - (flick.width - margin)) / margin))
            }
            if (dir === 0)
                return
            const limit = Math.max(0, flick.contentWidth - flick.width)
            const next = Math.max(0, Math.min(limit, flick.contentX + dir * (4 + depth * 12)))
            if (next === flick.contentX)
                return
            flick.contentX = next
            win.hot = hit(pointerX, pointerY)
        }
    }

    Timer {
        interval: 16
        repeat: true
        running: drag.active
        onTriggered: drag.nudgePages()
    }

    Shortcut {
        sequence: "Escape"
        enabled: drag.active
        context: Qt.ApplicationShortcut
        onActivated: drag.cancel()
    }
    Shortcut { sequence: "Ctrl+Z"; onActivated: controller.undo() }
    Shortcut { sequence: "Ctrl+Shift+Z"; onActivated: controller.redo() }
    Shortcut { sequence: "Ctrl+R"; onActivated: if (!controller.busy) controller.pull() }
    Shortcut { sequence: "Ctrl+,"; onActivated: openSettings() }
    Shortcut { sequence: "Ctrl+Return"; onActivated: if (controller.dirty && !controller.busy) confirmOpen = true }

    RowLayout {
        anchors.fill: parent
        anchors.bottomMargin: 32
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 248
            Layout.fillHeight: true
            color: "#101013"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                RowLayout {
                    spacing: 10
                    Image {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        source: "hearth.png"
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        mipmap: true
                    }
                    Column {
                        Text { text: "Hearth"; color: "white"; font.pixelSize: 18; font.bold: true }
                        Text { text: "Home screen"; color: "#8E8E93"; font.pixelSize: 11 }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.fillWidth: true
                        text: controller.deviceName || controller.linkLabel
                        color: "white"
                        font.pixelSize: 13
                        font.bold: true
                        elide: Text.ElideRight
                    }
                    Button {
                        objectName: "refreshDevice"
                        text: "Refresh"
                        enabled: !controller.busy
                        onClicked: controller.refreshDevice()
                        background: Rectangle { radius: 8; color: parent.hovered ? "#1C1C22" : "transparent"; border.color: "#3A3A40"; border.width: 1 }
                        contentItem: Text { text: parent.text; color: "#C7C7CC"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 11; leftPadding: 8; rightPadding: 8 }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: controller.subtitle || controller.linkDetail
                    color: "#8E8E93"
                    font.pixelSize: 11
                    visible: text !== ""
                    elide: Text.ElideRight
                }

                Rectangle {
                    id: driverCard
                    objectName: "driverCard"
                    property bool manualOpen: false
                    visible: controller.driverNeeded
                    Layout.fillWidth: true
                    implicitHeight: driverCol.implicitHeight + 20
                    radius: 10
                    color: "#1C1C22"
                    border.color: "#3A3A40"
                    border.width: 1
                    ColumnLayout {
                        id: driverCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 10
                        spacing: 8
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: controller.driverHeadline
                            color: "white"
                            font.pixelSize: 12
                            font.bold: true
                        }
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: controller.driverDetail
                            color: "#C7C7CC"
                            font.pixelSize: 11
                        }
                        Button {
                            Layout.fillWidth: true
                            visible: controller.driverAction !== ""
                            text: controller.driverAction
                            enabled: !controller.busy
                            onClicked: controller.installDriver()
                            background: Rectangle { radius: 8; color: parent.down ? "#0060D0" : "#0A84FF" }
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                font.bold: true
                                font.pixelSize: 12
                            }
                        }
                        Button {
                            objectName: "driverPageButton"
                            Layout.fillWidth: true
                            visible: controller.driverUrlAction !== ""
                            text: controller.driverUrlAction
                            enabled: !controller.busy
                            onClicked: controller.openDriverPage()
                            background: Rectangle { radius: 8; color: parent.down ? "#2C2C32" : "#3A3A40" }
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                font.pixelSize: 12
                            }
                        }
                        Text {
                            objectName: "manualToggle"
                            Layout.fillWidth: true
                            visible: controller.driverManual !== ""
                            text: driverCard.manualOpen ? "Hide manual steps" : "Show manual steps"
                            color: "#0A84FF"
                            font.pixelSize: 11
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: driverCard.manualOpen = !driverCard.manualOpen
                            }
                        }
                        ColumnLayout {
                            objectName: "manualSteps"
                            Layout.fillWidth: true
                            visible: controller.driverManual !== "" && driverCard.manualOpen
                            spacing: 6
                            Text {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                text: "Run this once on your computer if the button doesn't work."
                                color: "#C7C7CC"
                                font.pixelSize: 11
                            }
                            TextEdit {
                                Layout.fillWidth: true
                                readOnly: true
                                selectByMouse: true
                                wrapMode: Text.WrapAnywhere
                                text: controller.driverManual
                                color: "#8E8E93"
                                font.pixelSize: 10
                                font.family: "monospace"
                            }
                            Button {
                                Layout.fillWidth: true
                                text: "Copy"
                                onClicked: controller.copyDriverManual()
                                background: Rectangle { radius: 8; color: parent.down ? "#2C2C32" : "#3A3A40" }
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    font.pixelSize: 12
                                }
                            }
                        }
                    }
                }

                Button {
                    Layout.fillWidth: true
                    text: "Read from Device"
                    enabled: !controller.busy
                    onClicked: controller.pull()
                    background: Rectangle { radius: 10; color: parent.down ? "#2A2A30" : "#1C1C22"; border.color: "#3A3A40"; border.width: 1 }
                    contentItem: Text { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.bold: true }
                }
                Button {
                    Layout.fillWidth: true
                    text: controller.dirty ? "Send to Device" : "In sync"
                    enabled: controller.dirty && !controller.busy
                    onClicked: confirmOpen = true
                    background: Rectangle {
                        radius: 10
                        color: !parent.enabled ? "#1C1C22" : (parent.down ? "#0060D0" : "#0A84FF")
                    }
                    contentItem: Text {
                        text: parent.text
                        color: parent.enabled ? "white" : "#8E8E93"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.bold: true
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Button {
                        text: "Undo"
                        Layout.fillWidth: true
                        enabled: !controller.busy
                        onClicked: controller.undo()
                        background: Rectangle { radius: 8; color: parent.hovered ? "#1C1C22" : "transparent" }
                        contentItem: Text { text: parent.text; color: "#C7C7CC"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 12 }
                    }
                    Button {
                        text: "Redo"
                        Layout.fillWidth: true
                        enabled: !controller.busy
                        onClicked: controller.redo()
                        background: Rectangle { radius: 8; color: parent.hovered ? "#1C1C22" : "transparent" }
                        contentItem: Text { text: parent.text; color: "#C7C7CC"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: 12 }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32
                    radius: 10
                    color: "#1C1C22"
                    Row {
                        anchors.fill: parent
                        Repeater {
                            model: ["Move", "Group"]
                            delegate: Rectangle {
                                required property string modelData
                                required property int index
                                width: parent.width / 2
                                height: parent.height
                                radius: 10
                                color: (index === 1) === win.groupMode ? "#3A3A40" : "transparent"
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData
                                    color: "white"
                                    font.pixelSize: 12
                                    font.bold: true
                                }
                                MouseArea { anchors.fill: parent; onClicked: win.groupMode = index === 1 }
                            }
                        }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: groupMode
                        ? "Drop an app on another app to make a folder. Move mode places icons beside each other and can leave empty cells."
                        : "Drag an icon to move it. Drop it on an empty cell to leave a gap, or on the side of an icon to place it beside that icon. Drop on the middle of a folder to put it inside. Drag a name, or hold an icon at the side of the canvas, to slide the pages. Click a folder to open it underneath. Pull the folder handle down to close it."
                    color: "#8E8E93"
                    font.pixelSize: 11
                }

                Text { text: "Versions"; color: "#8E8E93"; font.pixelSize: 11; font.bold: true }
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 2
                    model: controller.versions
                    delegate: Rectangle {
                        required property var modelData
                        width: ListView.view.width
                        height: 28
                        radius: 6
                        color: hover.hovered ? "#1C1C22" : "transparent"
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            verticalAlignment: Text.AlignVCenter
                            text: modelData.label
                            color: "#C7C7CC"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                        HoverHandler { id: hover }
                        TapHandler { onTapped: controller.loadVersion(modelData.path) }
                    }
                }

                Button {
                    Layout.fillWidth: true
                    text: "Settings"
                    onClicked: openSettings()
                    background: Rectangle { radius: 10; color: parent.down ? "#2A2A30" : "transparent"; border.color: "#3A3A40"; border.width: 1 }
                    contentItem: Text { text: parent.text; color: "#C7C7CC"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
            }
        }

        Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: "#232328" }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    TextField {
                        id: search
                        Layout.fillWidth: true
                        placeholderText: "Find an app"
                        color: "white"
                        placeholderTextColor: "#8E8E93"
                        font.pixelSize: 14
                        background: Rectangle { radius: 10; color: "#16161A"; border.color: "#2A2A30"; border.width: 1 }
                        leftPadding: 12
                    }
                    Text {
                        text: controller.detail
                        color: "#8E8E93"
                        font.pixelSize: 12
                        elide: Text.ElideRight
                        Layout.maximumWidth: 360
                    }
                }

                Item {
                    id: stageHost
                    objectName: "stageHost"
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    readonly property bool folderOpen: (controller.folder.source || "") !== ""
                    property real dockReveal: folderOpen ? 1 : 0
                    property real trayReveal: folderOpen ? 1 : 0
                    readonly property real trayGap: 12
                    readonly property real trayWanted: Math.round(Math.min(360, Math.max(248, height * 0.34)))

                    Behavior on dockReveal {
                        NumberAnimation { duration: 360; easing.type: Easing.OutCubic }
                    }
                    Behavior on trayReveal {
                        NumberAnimation { duration: 360; easing.type: Easing.OutCubic }
                    }

                    Flickable {
                        id: stage
                        objectName: "stage"
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: (stageHost.trayWanted + stageHost.trayGap) * stageHost.dockReveal
                        contentWidth: phoneRow.x + phoneRow.width + 16
                        contentHeight: height
                        flickableDirection: Flickable.HorizontalFlick
                        boundsBehavior: Flickable.StopAtBounds
                        clip: true
                        z: 0

                        Row {
                            id: phoneRow
                            x: 8
                            height: stage.height
                            spacing: 22

                            Repeater {
                                id: phones
                                model: controller.layoutView.pages
                                delegate: Item {
                                    id: phoneSlot
                                    required property var modelData
                                    property alias phone: phone
                                    width: phone.width
                                    height: phoneRow.height

                                    PhonePage {
                                        id: phone
                                        objectName: "phone:" + modelData.index
                                        // One whole device stays inside the stage. Further pages scroll sideways.
                                        readonly property real availH: Math.max(1, stage.height - 8)
                                        readonly property real availW: Math.max(160, stage.width - 120)
                                        readonly property real fit: Math.min(availH / designH, availW / designW)
                                        page: modelData
                                        dock: controller.layoutView.dock
                                        columns: controller.layoutView.columns || 4
                                        dockSlots: controller.layoutView.dockSlots || 4
                                        chassisW: controller.layoutView.chassisW || 390
                                        chassisH: controller.layoutView.chassisH || 812
                                        island: controller.layoutView.island !== false
                                        wallpaper: controller.wallpaper
                                        groupMode: win.groupMode
                                        hot: win.hot
                                        selected: controller.selected
                                        dragApi: drag
                                        query: search.text
                                        width: designW * fit
                                        height: designH * fit
                                        y: {
                                            const centered = Math.max(0, (phoneSlot.height - height) / 2)
                                            return centered + (4 - centered) * stageHost.dockReveal
                                        }
                                    }
                                }
                            }

                            Item {
                                id: addSlot
                                width: 72
                                height: phoneRow.height
                                Rectangle {
                                    objectName: "addPage"
                                    width: 72
                                    radius: width / 2
                                    color: addHover.hovered ? "#1C1C22" : "#141418"
                                    border.color: "#3A3A40"
                                    height: {
                                        const hostH = stage.height
                                        const count = phones.count
                                        const slot = count > 0 ? phones.itemAt(0) : null
                                        const lead = slot ? slot.phone : null
                                        return lead ? lead.height * lead.chassisH / lead.designH : Math.max(48, hostH - 28)
                                    }
                                    y: {
                                        const hostH = stage.height
                                        const reveal = stageHost.dockReveal
                                        const count = phones.count
                                        const slot = count > 0 ? phones.itemAt(0) : null
                                        const lead = slot ? slot.phone : null
                                        if (!lead)
                                            return Math.max(0, (hostH - height) / 2)
                                        return lead.y + lead.height * (lead.labelH + lead.labelGap) / lead.designH + reveal * 0
                                    }
                                    Text { anchors.centerIn: parent; text: "+"; color: "white"; font.pixelSize: 28 }
                                    HoverHandler { id: addHover }
                                    TapHandler { onTapped: controller.addPage() }
                                }
                            }
                        }
                    }

                    FolderTray {
                        id: tray
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        height: stageHost.trayWanted * stageHost.trayReveal
                        anchors.bottomMargin: -tray.pull
                        z: 4
                        dragApi: drag
                        hot: win.hot
                        reveal: stageHost.trayReveal
                        wanted: stageHost.trayWanted
                    }
                }
            }
        }

        Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: "#232328" }

        Rectangle {
            Layout.preferredWidth: 360
            Layout.fillHeight: true
            color: "#101013"

            Flickable {
                id: sideFlick
                anchors.fill: parent
                contentWidth: width
                contentHeight: sideColumn.height + 28
                clip: true

                Column {
                    id: sideColumn
                    width: sideFlick.width - 32
                    x: 16
                    y: 16
                    spacing: 14

                    Text { text: "Organize"; color: "white"; font.pixelSize: 16; font.bold: true }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: "Say how you want it. The model proposes a layout. Applying it stays on this canvas until you send it."
                        color: "#8E8E93"
                        font.pixelSize: 12
                    }
                    Flow {
                        width: parent.width
                        spacing: 6
                        Repeater {
                            model: [
                                "One page of themed folders. Keep the dock. Widgets on their own page.",
                                "Keep these folders. Put each shortcut next to the app it belongs with.",
                                "Sort every folder by name."
                            ]
                            delegate: Rectangle {
                                required property string modelData
                                width: parent.width
                                height: label.implicitHeight + 12
                                radius: 12
                                color: "#1C1C22"
                                border.color: "#3A3A40"
                                Text {
                                    id: label
                                    x: 8
                                    y: 6
                                    width: parent.width - 16
                                    wrapMode: Text.WordWrap
                                    text: modelData
                                    color: "#C7C7CC"
                                    font.pixelSize: 11
                                }
                                MouseArea { anchors.fill: parent; onClicked: instruction.text = modelData }
                            }
                        }
                    }
                    ScrollView {
                        id: instructionView
                        width: parent.width
                        height: 110
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        TextArea {
                            id: instruction
                            width: instructionView.availableWidth
                            placeholderText: "Put games together. Keep the dock."
                            wrapMode: TextArea.Wrap
                            color: "white"
                            placeholderTextColor: "#6E6E73"
                            font.pixelSize: 13
                            background: Rectangle { radius: 10; color: "#1C1C22"; border.color: "#2A2A30"; border.width: 1 }
                            leftPadding: 10
                            rightPadding: 10
                            topPadding: 8
                            bottomPadding: 8
                        }
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: "Write a little or a lot. Describe the home screen you want."
                        color: "#8E8E93"
                        font.pixelSize: 12
                    }
                    Button {
                        width: parent.width
                        text: controller.busy ? "Working…" : "Reorganize"
                        enabled: !controller.busy
                        onClicked: controller.propose(instruction.text)
                        background: Rectangle { radius: 10; color: !parent.enabled ? "#1C1C22" : (parent.down ? "#0060D0" : "#0A84FF") }
                        contentItem: Text { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.bold: true }
                    }

                    Rectangle {
                        visible: controller.proposalSummary !== ""
                        width: parent.width
                        height: proposalColumn.height + 20
                        radius: 12
                        color: "#1C1C22"
                        Column {
                            id: proposalColumn
                            x: 10
                            y: 10
                            width: parent.width - 20
                            spacing: 6
                            Text {
                                width: parent.width
                                text: controller.proposalSummary
                                color: "white"
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                            }
                            Repeater {
                                model: controller.proposalLines
                                delegate: Text {
                                    required property string modelData
                                    width: proposalColumn.width
                                    text: modelData
                                    color: "#C7C7CC"
                                    font.pixelSize: 11
                                    wrapMode: Text.WordWrap
                                }
                            }
                            Row {
                                spacing: 8
                                visible: controller.proposalReady
                                Button {
                                    text: "Apply to canvas"
                                    onClicked: controller.applyProposal()
                                    background: Rectangle { radius: 8; color: "#30D158" }
                                    contentItem: Text { text: parent.text; color: "#04140A"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.bold: true; leftPadding: 10; rightPadding: 10 }
                                }
                                Button {
                                    text: "Discard"
                                    onClicked: controller.discardProposal()
                                    background: Rectangle { radius: 8; color: "transparent"; border.color: "#3A3A40"; border.width: 1 }
                                    contentItem: Text { text: parent.text; color: "#C7C7CC"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 10; rightPadding: 10 }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 32
        color: "#101013"
        Text {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            verticalAlignment: Text.AlignVCenter
            text: controller.status
            color: controller.error ? "#FF453A" : "#8E8E93"
            font.pixelSize: 12
            elide: Text.ElideRight
        }
    }

    Item {
        id: overlay
        anchors.fill: parent
        z: 10

        Item {
            id: ghost
            property string source: ""
            property string letter: ""
            property string ident: ""
            property string kind: "app"
            property Item sample: null
            property real holdX: 0
            property real holdY: 0
            visible: false
            enabled: false
            width: 68
            height: 68
            z: 2
            opacity: 0.92

            IconBadge {
                anchors.fill: parent
                visible: ghost.sample === null
                letter: ghost.letter
                ident: ghost.ident
                kind: ghost.kind
            }
            ShaderEffectSource {
                anchors.fill: parent
                sourceItem: ghost.sample
                live: ghost.visible && ghost.sample !== null
                hideSource: false
                smooth: true
                visible: ghost.sample !== null
            }
        }
    }

    UpdateNotice {
        id: updateNotice
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 16
        anchors.bottomMargin: 32 + 16
        z: 19
        shown: controller.updateAvailable
        version: controller.updateVersion
        current: controller.appVersion
        onDownload: controller.openUpdatePage()
        onLater: controller.dismissUpdate()
        onSkip: controller.skipUpdate()
    }

    Rectangle {
        visible: settingsOpen
        anchors.fill: parent
        color: "#99000000"
        z: 20
        MouseArea { anchors.fill: parent; onClicked: settingsOpen = false }

        Rectangle {
            id: settingsCard
            anchors.centerIn: parent
            width: 460
            height: Math.min(settingsColumn.height + 36, parent.height - 48)
            radius: 16
            color: "#16161A"
            border.color: "#3A3A40"
            Flickable {
                id: settingsFlick
                anchors.fill: parent
                anchors.margins: 18
                contentHeight: settingsColumn.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds
            Column {
                id: settingsColumn
                width: settingsFlick.width
                spacing: 10
                Text { text: "LLM Model"; color: "white"; font.pixelSize: 18; font.bold: true }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Grok can sign in. The other providers take an API key, which stays on this computer."
                    color: "#8E8E93"
                    font.pixelSize: 12
                }
                Text { text: "Provider"; color: "#8E8E93"; font.pixelSize: 11 }
                ComboBox {
                    id: providerBox
                    width: parent.width
                    textRole: "name"
                    valueRole: "id"
                    model: controller.providerPresets
                    background: Rectangle { radius: 8; color: "#1C1C22" }
                    contentItem: Text {
                        text: providerBox.displayText
                        color: "white"
                        leftPadding: 10
                        verticalAlignment: Text.AlignVCenter
                    }
                    onActivated: applyPreset(currentValue, !win.fillingSettings)
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    visible: providerHint !== ""
                    text: providerHint
                    color: "#8E8E93"
                    font.pixelSize: 12
                }
                Text {
                    visible: providerDocs !== ""
                    text: "API key page"
                    color: "#0A84FF"
                    font.pixelSize: 12
                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -4
                        cursorShape: Qt.PointingHandCursor
                        onClicked: Qt.openUrlExternally(providerDocs)
                    }
                }
                Column {
                    width: parent.width
                    spacing: 8
                    visible: providerIsGrok
                    Button {
                        text: controller.grokSignedIn ? "Sign out of Grok" : "Sign in with Grok"
                        enabled: !controller.busy
                        onClicked: controller.grokSignedIn ? controller.signOutGrok() : controller.startGrokSignIn()
                        background: Rectangle { radius: 8; color: parent.enabled ? "#1C1C22" : "#141418"; border.color: "#3A3A40"; border.width: 1 }
                        contentItem: Text { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                    }
                    Text {
                        visible: controller.grokCode !== ""
                        text: controller.grokCode
                        color: "white"
                        font.pixelSize: 22
                        font.bold: true
                        font.letterSpacing: 2
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        visible: controller.grokCode !== ""
                        text: "Enter this code on the page that opened."
                        color: "#C7C7CC"
                        font.pixelSize: 12
                    }
                }
                Text { text: "Endpoint"; color: "#8E8E93"; font.pixelSize: 11 }
                TextField {
                    id: endpoint
                    width: parent.width
                    color: "white"
                    placeholderText: "https://api.x.ai/v1"
                    background: Rectangle { radius: 8; color: "#1C1C22" }
                    leftPadding: 10
                }
                Text { visible: keyVisible; text: "API key"; color: "#8E8E93"; font.pixelSize: 11 }
                TextField {
                    id: keyField
                    visible: keyVisible
                    width: parent.width
                    echoMode: TextInput.Password
                    color: "white"
                    placeholderText: controller.keyHint
                    background: Rectangle { radius: 8; color: "#1C1C22" }
                    leftPadding: 10
                }
                Text { visible: keyVisible; text: controller.keyHint; color: "#6E6E73"; font.pixelSize: 11 }
                CheckBox {
                    id: forgetKey
                    visible: keyVisible
                    text: "Forget the saved key"
                    contentItem: Text {
                        text: forgetKey.text
                        color: "#C7C7CC"
                        leftPadding: forgetKey.indicator.width + 8
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                Text { text: "LLM Model"; color: "#8E8E93"; font.pixelSize: 11 }
                ComboBox {
                    id: modelBox
                    width: parent.width
                    editable: true
                    model: controller.modelChoices
                    background: Rectangle { radius: 8; color: "#1C1C22" }
                    contentItem: Text {
                        text: modelBox.editText
                        color: "white"
                        leftPadding: 10
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                Text { text: "Updates"; color: "white"; font.pixelSize: 18; font.bold: true; topPadding: 8 }
                CheckBox {
                    id: updatesBox
                    objectName: "updatesBox"
                    text: "Check for updates on startup"
                    onToggled: controller.setCheckUpdates(checked)
                    contentItem: Text {
                        text: updatesBox.text
                        color: "#C7C7CC"
                        leftPadding: updatesBox.indicator.width + 8
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Hearth asks GitHub once a day whether a newer version exists. Nothing else is sent."
                    color: "#6E6E73"
                    font.pixelSize: 11
                }
                Row {
                    spacing: 8
                    Button {
                        text: "Refresh models"
                        onClicked: {
                            controller.saveSettings(providerBox.currentValue, endpoint.text, keyField.text, modelBox.editText, false)
                            controller.refreshModels()
                        }
                        background: Rectangle { radius: 8; color: "#1C1C22"; border.color: "#3A3A40"; border.width: 1 }
                        contentItem: Text { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
                    }
                    Button {
                        text: "Save"
                        onClicked: {
                            controller.saveSettings(providerBox.currentValue, endpoint.text, keyField.text, modelBox.editText, forgetKey.checked)
                            settingsOpen = false
                        }
                        background: Rectangle { radius: 8; color: "#0A84FF" }
                        contentItem: Text { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.bold: true; leftPadding: 16; rightPadding: 16 }
                    }
                    Button {
                        text: "Close"
                        onClicked: settingsOpen = false
                        background: Rectangle { color: "transparent" }
                        contentItem: Text { text: parent.text; color: "#8E8E93"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 8; rightPadding: 8 }
                    }
                }
            }
            }
        }
    }

    Rectangle {
        visible: confirmOpen
        anchors.fill: parent
        color: "#99000000"
        z: 21
        MouseArea { anchors.fill: parent; onClicked: confirmOpen = false }

        Rectangle {
            anchors.centerIn: parent
            width: 420
            height: confirmColumn.height + 36
            radius: 16
            color: "#16161A"
            border.color: "#3A3A40"
            MouseArea { anchors.fill: parent }
            Column {
                id: confirmColumn
                z: 1
                x: 18
                y: 18
                width: parent.width - 36
                spacing: 12
                Text { text: "Send this layout?"; color: "white"; font.pixelSize: 18; font.bold: true }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "This replaces the home screen on the connected iPhone or iPad. A backup is saved first. The device is read back, and if the layout does not stick the previous one is restored."
                        + (controller.hasHoles ? " Gaps on a page stay in this editor. Sending closes them, because the phone's layout list has no empty cells." : "")
                    color: "#C7C7CC"
                    font.pixelSize: 13
                }
                Row {
                    spacing: 8
                    Button {
                        text: "Send to Device"
                        onClicked: { confirmOpen = false; controller.push() }
                        background: Rectangle { radius: 8; color: "#0A84FF" }
                        contentItem: Text { text: parent.text; color: "white"; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 16; rightPadding: 16 }
                    }
                    Button {
                        text: "Cancel"
                        onClicked: confirmOpen = false
                        background: Rectangle { radius: 8; color: "transparent"; border.color: "#3A3A40"; border.width: 1 }
                        contentItem: Text { text: parent.text; color: "#C7C7CC"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 16; rightPadding: 16 }
                    }
                }
            }
        }
    }

    Timer {
        interval: 2000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: controller.checkDevice()
    }
}
