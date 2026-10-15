import QtQuick
import QtQuick.Controls

// The open folder. The phone sits above this strip. Pages scroll sideways,
// and icons drag between those pages, the home screen, and the dock.
Rectangle {
    id: tray

    property var dragApi
    property string hot: ""
    property real reveal: 0
    property real wanted: 280

    objectName: "folderTray"
    radius: 18
    color: "#121216"
    border.color: "#2A2A30"
    border.width: 1
    clip: true
    antialiasing: true
    opacity: Math.min(1, Math.max(0, reveal * 1.35))
    enabled: height > 36

    readonly property real cardSide: Math.max(96, wanted - 78)

    function folderTarget(flat) {
        const tail = (controller.folder.source || "").slice(5)
        const total = controller.folder.count || 0
        if (flat >= total)
            return "at:folder:" + tail + ":end"
        return "at:folder:" + tail + ":" + flat
    }

    function blocks(scenePoint) {
        if (height < 24 || opacity < 0.25)
            return false
        const local = mapFromItem(null, scenePoint.x, scenePoint.y)
        return local.x >= 0 && local.y >= 0 && local.x < width && local.y < height
    }

    function targetAt(scenePoint) {
        if (!blocks(scenePoint))
            return ""
        const pages = controller.folder.pages || []
        for (let i = 0; i < pageRow.count; i++) {
            const card = pageRow.itemAt(i)
            if (!card || !card.grid)
                continue
            const local = card.grid.mapFromItem(null, scenePoint.x, scenePoint.y)
            if (local.x < 0 || local.y < 0 || local.x >= card.grid.width || local.y >= card.grid.height)
                continue
            return card.dropTarget(local, pages[i])
        }
        return ""
    }

    function syncName() {
        if (nameField.activeFocus)
            return
        nameField.text = controller.folder.name || ""
    }

    property string openSource: controller.folder.source || ""
    onOpenSourceChanged: folderFlick.contentX = 0
    Component.onCompleted: syncName()

    Connections {
        target: controller
        function onFolderChanged() { tray.syncName() }
    }

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 7
        width: 36
        height: 4
        radius: 2
        color: "#55FFFFFF"
    }

    Row {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        anchors.topMargin: 18
        spacing: 8

        TextField {
            id: nameField
            width: Math.max(80, header.width - countLabel.width - closeButton.width - header.spacing * 2)
            height: 36
            color: "white"
            font.pixelSize: 15
            font.bold: true
            background: Rectangle { radius: 10; color: "#1C1C22" }
            leftPadding: 10
            verticalAlignment: TextInput.AlignVCenter
            onEditingFinished: controller.renameFolder(text)
        }
        Text {
            id: countLabel
            width: implicitWidth
            height: 36
            text: (controller.folder.count || 0) + " inside"
            color: "#8E8E93"
            font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
        }
        Rectangle {
            id: closeButton
            objectName: "folderClose"
            width: closeText.implicitWidth + 22
            height: 36
            radius: 10
            color: closeHover.containsMouse ? "#2A2A30" : "transparent"
            Text {
                id: closeText
                anchors.centerIn: parent
                text: "Close"
                color: "#0A84FF"
                font.pixelSize: 12
                font.bold: true
            }
            MouseArea {
                id: closeHover
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: controller.closeFolder()
            }
        }
    }

    Flickable {
        id: folderFlick
        objectName: "folderPages"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.topMargin: 10
        anchors.bottomMargin: 12
        contentWidth: Math.max(width, pageStrip.width + 16)
        contentHeight: Math.max(height, pageStrip.height)
        flickableDirection: Flickable.HorizontalFlick
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Row {
            id: pageStrip
            x: Math.max(4, (folderFlick.width - width) / 2)
            y: Math.max(0, (folderFlick.height - height) / 2)
            height: tray.cardSide
            spacing: 14

            Repeater {
                id: pageRow
                model: controller.folder.pages || []
                delegate: Rectangle {
                    id: card
                    required property var modelData
                    required property int index
                    property alias grid: grid
                    width: tray.cardSide
                    height: tray.cardSide
                    radius: 22
                    color: "#1A1A20"
                    border.color: "#2E2E36"
                    border.width: 1
                    antialiasing: true

                    function dropTarget(local, page) {
                        const cellW = Math.max(1, grid.width / 3)
                        const cellH = Math.max(1, grid.height / 3)
                        let col = Math.floor(local.x / cellW)
                        let row = Math.floor(local.y / cellH)
                        if (col < 0) col = 0
                        if (row < 0) row = 0
                        if (col > 2) col = 2
                        if (row > 2) row = 2
                        const slot = row * 3 + col
                        const frac = (local.x - col * cellW) / cellW
                        const tiles = (page && page.tiles) || []
                        for (let i = 0; i < tiles.length; i++) {
                            if (tiles[i].slot !== slot)
                                continue
                            const dest = frac >= 0.5 ? tiles[i].flat + 1 : tiles[i].flat
                            return tray.folderTarget(dest)
                        }
                        const cells = (page && page.cells) || []
                        return cells[slot] ? cells[slot].target : ""
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 8
                        text: index + 1
                        color: "#5C5C66"
                        font.pixelSize: 11
                        font.bold: true
                    }

                    Item {
                        id: grid
                        anchors.fill: parent
                        anchors.margins: 14
                        anchors.topMargin: 18

                        Repeater {
                            model: modelData.cells || []
                            delegate: Item {
                                id: cellPad
                                required property var modelData
                                x: (modelData.slot % 3) * (grid.width / 3)
                                y: Math.floor(modelData.slot / 3) * (grid.height / 3)
                                width: grid.width / 3
                                height: grid.height / 3
                                readonly property real iconSide: Math.min(width - 8, Math.max(8, height - 20))

                                Rectangle {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.top: parent.top
                                    anchors.topMargin: 2
                                    width: cellPad.iconSide
                                    height: width
                                    radius: width * 0.2237
                                    color: tray.hot !== "" && tray.hot === modelData.target ? "#330A84FF" : (modelData.empty ? "#14FFFFFF" : "transparent")
                                }
                            }
                        }

                        Repeater {
                            model: modelData.tiles || []
                            delegate: Item {
                                id: slotItem
                                required property var modelData
                                x: (modelData.slot % 3) * (grid.width / 3)
                                y: Math.floor(modelData.slot / 3) * (grid.height / 3)
                                width: grid.width / 3
                                height: grid.height / 3

                                Rectangle {
                                    visible: tray.hot !== "" && tray.hot === tray.folderTarget(modelData.flat)
                                    width: 3
                                    height: Math.max(8, icon.height * 0.62)
                                    radius: 2
                                    color: "#0A84FF"
                                    anchors.verticalCenter: icon.verticalCenter
                                    // Cell edges meet halfway between the two icon squares.
                                    anchors.horizontalCenter: parent.left
                                }
                                Rectangle {
                                    visible: tray.hot !== "" && modelData.flat + 1 >= (controller.folder.count || 0) && tray.hot === tray.folderTarget(modelData.flat + 1)
                                    width: 3
                                    height: Math.max(8, icon.height * 0.62)
                                    radius: 2
                                    color: "#0A84FF"
                                    anchors.verticalCenter: icon.verticalCenter
                                    anchors.horizontalCenter: parent.right
                                }

                                IconBadge {
                                    id: icon
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.top: parent.top
                                    anchors.topMargin: 2
                                    width: Math.min(parent.width - 8, Math.max(8, parent.height - 20))
                                    height: width
                                    ident: modelData.ident
                                    letter: modelData.letter
                                    kind: modelData.kind
                                }
                                Text {
                                    anchors.top: icon.bottom
                                    anchors.topMargin: 2
                                    width: parent.width
                                    horizontalAlignment: Text.AlignHCenter
                                    text: modelData.name
                                    color: "white"
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                }
                                DragSpot {
                                    anchors.fill: icon
                                    moves: true
                                    sample: icon
                                    dragApi: tray.dragApi
                                    source: modelData.source
                                    letter: modelData.letter
                                    ident: modelData.ident
                                    kind: modelData.kind
                                }
                                DragSpot {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: icon.bottom
                                    anchors.bottom: parent.bottom
                                    moves: false
                                    passPan: true
                                    dragApi: tray.dragApi
                                    source: modelData.source
                                    letter: modelData.letter
                                    ident: modelData.ident
                                    kind: modelData.kind
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
