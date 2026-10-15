import QtQuick

// The picture of an icon, folder, or widget starts a move. The name under it
// does not: inside the page strip that gesture pans, and elsewhere it slides
// the page strip by hand so a parent scroller cannot take the drag.
// Right-click or Escape cancels a move. The picture keeps the icon's size.
MouseArea {
    id: spot

    property bool moves: true
    property bool passPan: true
    property var pages
    property var dragApi
    property Item sample: null
    property string source: ""
    property string letter: ""
    property string ident: ""
    property string kind: "app"

    objectName: source ? (moves ? "icon:" : "name:") + source : ""
    preventStealing: moves || !passPan
    cursorShape: moves
        ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor)
        : Qt.SizeHorCursor
    acceptedButtons: Qt.LeftButton | Qt.RightButton

    property bool moved: false
    property bool dragging: false
    property bool suppressed: false
    property real originX: 0
    property real originY: 0
    property real lastX: 0

    function scenePoint(mouse) {
        return mapToItem(null, mouse.x, mouse.y)
    }

    function stopDrag() {
        suppressed = true
        if (dragging && dragApi)
            dragApi.cancel()
        dragging = false
    }

    onPressed: (mouse) => {
        if (mouse.button === Qt.RightButton) {
            if (dragging)
                stopDrag()
            return
        }
        suppressed = false
        moved = false
        dragging = false
        const point = scenePoint(mouse)
        originX = point.x
        originY = point.y
        lastX = point.x
    }

    onPositionChanged: (mouse) => {
        if (!pressed || suppressed)
            return
        if (mouse.buttons & Qt.RightButton) {
            if (dragging)
                stopDrag()
            return
        }
        const point = scenePoint(mouse)
        if (!moved && (Math.abs(point.x - originX) > 10 || Math.abs(point.y - originY) > 10))
            moved = true
        if (!moved)
            return
        if (moves) {
            if (!dragging) {
                dragging = true
                const pictured = sample || spot
                const local = pictured.mapFromItem(spot, mouse.x, mouse.y)
                if (dragApi)
                    dragApi.begin(source, letter, ident, kind, point.x, point.y, pictured, local.x, local.y)
            } else if (dragApi) {
                dragApi.move(point.x, point.y)
            }
        } else if (!passPan && pages) {
            const limit = Math.max(0, pages.contentWidth - pages.width)
            pages.contentX = Math.max(0, Math.min(limit, pages.contentX - (point.x - lastX)))
        }
        lastX = point.x
    }

    onReleased: (mouse) => {
        if (mouse.button !== Qt.LeftButton)
            return
        if (dragging && dragApi && !suppressed) {
            const point = scenePoint(mouse)
            dragApi.end(point.x, point.y)
        }
        dragging = false
        suppressed = false
    }

    onCanceled: {
        if (dragging && dragApi)
            dragApi.cancel()
        dragging = false
        suppressed = true
        moved = false
    }

    onClicked: (mouse) => {
        if (mouse.button !== Qt.LeftButton || moved || !source)
            return
        if (kind === "folder")
            controller.openFolder(source)
        else
            controller.select(source)
    }

    Connections {
        target: dragApi
        function onAborted() {
            if (spot.pressed || spot.dragging) {
                spot.dragging = false
                spot.suppressed = true
            }
        }
    }
}
