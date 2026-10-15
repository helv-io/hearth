import QtQuick

// Red page count on a folder. One page draws nothing.
Rectangle {
    id: badge

    property int pages: 0
    property real side: 16

    visible: pages >= 2
    color: "#FF3B30"
    height: Math.max(12, side)
    width: Math.max(height, caption.implicitWidth + height * 0.5)
    radius: height / 2
    antialiasing: true

    Text {
        id: caption
        anchors.centerIn: parent
        text: badge.pages
        color: "white"
        font.bold: true
        font.pixelSize: Math.max(1, badge.height * 0.62)
    }
}
