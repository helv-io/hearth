import QtQuick

Item {
    id: root
    property var page
    property var dock: []
    property string wallpaper: ""
    property bool groupMode: false
    property string hot: ""
    property string selected: ""
    property string query: ""
    property var dragApi

    // iPhone default: 15 Pro Max body, 76.7 × 159.9 mm, drawn at 390 × 812.
    // An iPad passes its own chassis. One device still fills the stage.
    property real chassisW: 390
    property real chassisH: 812
    property int columns: 4
    property int dockSlots: 4
    property bool island: true
    readonly property real labelH: 18
    readonly property real labelGap: 8
    readonly property real designW: chassisW
    readonly property real designH: labelH + labelGap + chassisH
    readonly property real u: width > 0 ? width / designW : 1

    // The middle of a folder face accepts a drop. The sides, and the gap after
    // the icon, insert before or after it so two neighbors can be split.
    function inFolderMouth(tile, local) {
        const strideX = grid.cw + grid.gap
        const strideY = grid.ch + grid.gap
        const tileW = tile.w * grid.cw + (tile.w - 1) * grid.gap
        const tileH = tile.h * grid.ch + (tile.h - 1) * grid.gap
        const face = Math.min(tileW, Math.max(1, tileH - 18 * root.u))
        const faceLeft = tile.col * strideX + (tileW - face) / 2
        const faceTop = tile.row * strideY
        const lx = local.x - faceLeft
        const ly = local.y - faceTop
        return lx >= face * 0.25 && lx <= face * 0.75 && ly >= face * 0.25 && ly <= face * 0.75
    }

    function targetAt(scenePoint, grouping) {
        const barPoint = dockBar.mapFromItem(null, scenePoint.x, scenePoint.y)
        if (dockBar.contains(barPoint)) {
            const local = dockRow.mapFromItem(null, scenePoint.x, scenePoint.y)
            const slots = Math.max(1, root.dockSlots)
            const slotW = Math.max(1, dockRow.width / slots)
            let slot = Math.floor(local.x / slotW)
            if (slot < 0)
                slot = 0
            if (slot > slots - 1)
                slot = slots - 1
            const tile = root.dock[slot]
            if (!tile)
                return ""
            if (tile.empty)
                return tile.target || ""
            const frac = (local.x - slot * slotW) / slotW
            if (frac >= 0.5) {
                const next = slot + 1
                if (next >= slots || !root.dock[next] || root.dock[next].empty)
                    return "at:dock:end"
                return "at:dock:" + next
            }
            return tile.target || ""
        }
        const local = grid.mapFromItem(null, scenePoint.x, scenePoint.y)
        if (!grid.contains(local))
            return ""
        const strideX = grid.cw + grid.gap
        const strideY = grid.ch + grid.gap
        const col = Math.floor(local.x / strideX)
        const row = Math.floor(local.y / strideY)
        if (col < 0 || row < 0 || col >= root.columns || row >= root.page.rows)
            return ""
        const tiles = root.page.tiles || []
        for (let i = 0; i < tiles.length; i++) {
            const tile = tiles[i]
            if (col < tile.col || col >= tile.col + tile.w || row < tile.row || row >= tile.row + tile.h)
                continue
            if (grouping && tile.onto)
                return tile.onto
            if (tile.kind === "folder" && inFolderMouth(tile, local))
                return tile.onto
            const slotWidth = Math.max(1, tile.w * strideX)
            const frac = (local.x - tile.col * strideX) / slotWidth
            return frac >= 0.5 ? (tile.after || "") : (tile.insert || "")
        }
        const cells = root.page.cells || []
        for (let c = 0; c < cells.length; c++) {
            if (cells[c].row === row && cells[c].col === col)
                return cells[c].target
        }
        return ""
    }

    Column {
        id: column
        anchors.fill: parent
        spacing: root.labelGap * root.u

        Text {
            id: pageLabel
            width: parent.width
            height: root.labelH * root.u
            text: "Page " + (root.page.index + 1) + (root.page.overflow ? "  ·  too full" : "")
            color: root.page.overflow ? "#FF453A" : "#8E8E93"
            font.pixelSize: Math.max(1, 12 * root.u)
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        Item {
            id: chassis
            width: parent.width
            height: parent.height - pageLabel.height - column.spacing

            Rectangle {
                anchors.fill: parent
                radius: 42 * root.u
                color: "#050506"
                border.color: root.page.overflow ? "#FF453A" : "#3A3A40"
                border.width: Math.max(1, 2 * root.u)
                antialiasing: true

                Rectangle {
                    id: screen
                    anchors.fill: parent
                    anchors.margins: 8 * root.u
                    radius: 34 * root.u
                    clip: true
                    color: "#000"
                    antialiasing: true

                    Item {
                        id: wallpaperFill
                        anchors.fill: parent
                        layer.enabled: true
                        layer.smooth: true
                        layer.effect: ShaderEffect {
                            fragmentShader: "roundclip.frag.qsb"
                            property real radius: screen.radius
                            property real itemWidth: wallpaperFill.width
                            property real itemHeight: wallpaperFill.height
                        }

                        Image {
                            anchors.fill: parent
                            source: root.wallpaper
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                        }
                        Rectangle {
                            anchors.fill: parent
                            color: "#59000000"
                        }
                    }
                    Rectangle {
                        visible: root.island
                        width: 96 * root.u
                        height: 28 * root.u
                        radius: 14 * root.u
                        color: "#000"
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.topMargin: 10 * root.u
                    }

                    Item {
                        id: grid
                        objectName: "grid:" + root.page.index
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.bottom: dockBar.top
                        anchors.leftMargin: 16 * root.u
                        anchors.rightMargin: 16 * root.u
                        anchors.topMargin: (root.island ? 52 : 28) * root.u
                        anchors.bottomMargin: 8 * root.u
                        property real gap: 8 * root.u
                        property int rowCount: root.page.rows || 6
                        property int columnCount: Math.max(1, root.columns)
                        property real cw: (width - (columnCount - 1) * gap) / columnCount
                        property real ch: (height - (rowCount - 1) * gap) / rowCount

                        Repeater {
                            model: root.page.cells
                            delegate: Item {
                                required property var modelData
                                x: modelData.col * (grid.cw + grid.gap)
                                y: modelData.row * (grid.ch + grid.gap)
                                width: grid.cw
                                height: grid.ch
                                // Same square the app icon uses. The cell itself is taller, for the name.
                                Rectangle {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.top: parent.top
                                    width: Math.min(parent.width, Math.max(1, parent.height - 18 * root.u))
                                    height: width
                                    radius: width * 0.2237
                                    color: root.hot === modelData.target ? "#3A0A84FF" : "transparent"
                                    border.width: root.hot === modelData.target ? Math.max(1, root.u) : 0
                                    border.color: "#0A84FF"
                                }
                            }
                        }

                        Repeater {
                            model: root.page.tiles
                            delegate: Item {
                                id: tile
                                required property var modelData
                                opacity: root.query === "" || (modelData.search || modelData.name || "").indexOf(root.query.toLowerCase()) !== -1 ? 1 : 0.16
                                x: modelData.col * (grid.cw + grid.gap)
                                y: modelData.row * (grid.ch + grid.gap)
                                width: modelData.w * grid.cw + (modelData.w - 1) * grid.gap
                                height: modelData.h * grid.ch + (modelData.h - 1) * grid.gap

                                Rectangle {
                                    x: modelData.kind === "widget" ? face.x : 0
                                    y: modelData.kind === "widget" ? face.y : 0
                                    width: modelData.kind === "widget" ? face.width : parent.width
                                    height: modelData.kind === "widget" ? face.height : parent.height
                                    radius: modelData.kind === "widget" ? face.width * 0.2 : 0
                                    color: "transparent"
                                    border.width: root.selected === modelData.source || root.hot === modelData.onto ? Math.max(1, 2 * root.u) : 0
                                    border.color: root.selected === modelData.source ? "#FFFFFF" : "#0A84FF"
                                }

                                Item {
                                    id: face
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.top: parent.top
                                    width: Math.min(parent.width, Math.max(1, parent.height - 18 * root.u))
                                    height: width

                                    Rectangle {
                                        visible: modelData.kind === "folder"
                                        anchors.fill: parent
                                        radius: width * 0.22
                                        color: "#38FFFFFF"
                                        Item {
                                            id: mini
                                            anchors.fill: parent
                                            property real inset: width * 0.16
                                            property real gap: width * 0.055
                                            property real side: (width - inset * 2 - gap * 2) / 3
                                            Repeater {
                                                model: modelData.preview
                                                delegate: IconBadge {
                                                    required property var modelData
                                                    required property int index
                                                    x: mini.inset + (index % 3) * (mini.side + mini.gap)
                                                    y: mini.inset + Math.floor(index / 3) * (mini.side + mini.gap)
                                                    width: mini.side
                                                    height: mini.side
                                                    ident: modelData
                                                    kind: "app"
                                                }
                                            }
                                        }
                                    }

                                    IconBadge {
                                        visible: modelData.kind === "app" || modelData.kind === "shortcut"
                                        anchors.fill: parent
                                        ident: modelData.ident
                                        letter: modelData.letter
                                        kind: modelData.kind
                                    }

                                    Item {
                                        id: widgetCard
                                        visible: modelData.kind === "widget"
                                        anchors.fill: parent
                                        layer.enabled: visible
                                        layer.smooth: true
                                        layer.effect: ShaderEffect {
                                            fragmentShader: "roundclip.frag.qsb"
                                            property real radius: widgetCard.width * 0.2
                                            property real itemWidth: widgetCard.width
                                            property real itemHeight: widgetCard.height
                                        }

                                        Rectangle {
                                            anchors.fill: parent
                                            color: "#F01C1C1E"
                                        }
                                        IconBadge {
                                            anchors.centerIn: parent
                                            width: parent.width * 1.35
                                            height: parent.height * 1.35
                                            opacity: 0.34
                                            ident: modelData.ident
                                            letter: modelData.letter
                                            kind: "widget"
                                        }
                                        Text {
                                            anchors.fill: parent
                                            anchors.margins: widgetCard.width * 0.08
                                            text: modelData.name
                                            color: "white"
                                            font.pixelSize: Math.max(1, widgetCard.width * 0.15)
                                            font.bold: true
                                            fontSizeMode: Text.HorizontalFit
                                            minimumPixelSize: 1
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                            style: Text.Raised
                                            styleColor: "#E6000000"
                                        }
                                        Rectangle {
                                            anchors.fill: parent
                                            radius: width * 0.2
                                            color: "transparent"
                                            border.color: "#33FFFFFF"
                                            border.width: Math.max(1, root.u)
                                            antialiasing: true
                                        }
                                    }
                                }

                                Text {
                                    anchors.top: face.bottom
                                    anchors.topMargin: 3 * root.u
                                    width: parent.width
                                    horizontalAlignment: Text.AlignHCenter
                                    text: modelData.kind === "widget" ? "Widget" : modelData.name
                                    color: "white"
                                    font.pixelSize: Math.max(1, 11 * root.u)
                                    elide: Text.ElideRight
                                }

                                Rectangle {
                                    visible: root.hot !== "" && root.hot === modelData.insert
                                    z: 4
                                    width: Math.max(3, 4 * root.u)
                                    height: Math.max(8, face.height * 0.62)
                                    radius: width / 2
                                    color: "#0A84FF"
                                    anchors.verticalCenter: face.verticalCenter
                                    anchors.horizontalCenter: parent.left
                                    // The gap lives outside the tile. Half of it puts the mark between the icons.
                                    anchors.horizontalCenterOffset: -grid.gap / 2
                                }
                                Rectangle {
                                    visible: root.hot !== "" && modelData.after && root.hot === modelData.after && modelData.after !== modelData.insert
                                    z: 4
                                    width: Math.max(3, 4 * root.u)
                                    height: Math.max(8, face.height * 0.62)
                                    radius: width / 2
                                    color: "#0A84FF"
                                    anchors.verticalCenter: face.verticalCenter
                                    anchors.horizontalCenter: parent.right
                                    anchors.horizontalCenterOffset: grid.gap / 2
                                }
                                DragSpot {
                                    anchors.fill: face
                                    moves: true
                                    sample: face
                                    dragApi: root.dragApi
                                    source: modelData.source
                                    letter: modelData.letter
                                    ident: modelData.ident
                                    kind: modelData.kind
                                }
                                DragSpot {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: face.bottom
                                    anchors.bottom: parent.bottom
                                    moves: false
                                    passPan: true
                                    dragApi: root.dragApi
                                    source: modelData.source
                                    letter: modelData.letter
                                    ident: modelData.ident
                                    kind: modelData.kind
                                }
                            }
                        }
                    }

                    Rectangle {
                        id: dockBar
                        objectName: "dockBar:" + root.page.index
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.margins: 12 * root.u
                        height: 74 * root.u
                        radius: 26 * root.u
                        color: "#2EFFFFFF"

                        Row {
                            id: dockRow
                            anchors.fill: parent
                            anchors.margins: 8 * root.u
                            spacing: 0
                            Repeater {
                                model: root.dock
                                delegate: Item {
                                    required property var modelData
                                    required property int index
                                    width: dockRow.width / Math.max(1, root.dockSlots)
                                    height: parent.height
                                    opacity: modelData.empty || root.query === "" || (modelData.search || "").indexOf(root.query.toLowerCase()) !== -1 ? 1 : 0.16
                                    property real iconSide: {
                                        const roomy = Math.min(width - 16 * root.u, height - 8 * root.u)
                                        if (roomy > 4)
                                            return roomy
                                        return Math.max(1, Math.min(width - 2, height - 4))
                                    }
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: parent.iconSide
                                        height: width
                                        radius: width * 0.2237
                                        color: root.hot === modelData.target ? "#3A0A84FF" : "transparent"
                                    }
                                    IconBadge {
                                        id: dockIcon
                                        visible: !modelData.empty
                                        anchors.centerIn: parent
                                        width: parent.iconSide
                                        height: width
                                        ident: modelData.ident || ""
                                        letter: modelData.letter || ""
                                        kind: modelData.kind || "app"
                                    }
                                    DragSpot {
                                        anchors.fill: parent
                                        enabled: !modelData.empty
                                        moves: true
                                        sample: dockIcon
                                        dragApi: root.dragApi
                                        source: modelData.source || ""
                                        letter: modelData.letter || ""
                                        ident: modelData.ident || ""
                                        kind: modelData.kind || "app"
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 6 * root.u
                        width: 96 * root.u
                        height: Math.max(1, 4 * root.u)
                        radius: 2 * root.u
                        color: "#CCFFFFFF"
                    }
                }
            }

            Text {
                visible: root.page.empty
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 14 * root.u
                text: "Remove"
                color: "#0A84FF"
                font.pixelSize: Math.max(1, 12 * root.u)
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -6 * root.u
                    onClicked: controller.deletePage(root.page.index)
                }
            }
        }
    }
}
