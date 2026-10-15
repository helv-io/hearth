import QtQuick

Item {
    id: root
    property string ident: ""
    property string letter: ""
    property string kind: "app"

    Image {
        id: photo
        anchors.fill: parent
        asynchronous: true
        cache: true
        mipmap: true
        fillMode: Image.PreserveAspectCrop
        smooth: true
        source: {
            const revision = controller.iconRev
            return root.ident ? controller.iconUrl(root.ident) : ""
        }
        visible: status === Image.Ready
    }

    Rectangle {
        anchors.fill: parent
        radius: width * 0.2237
        visible: photo.status !== Image.Ready
        color: root.kind === "shortcut" ? "#0A84FF" : (root.kind === "widget" ? "#2C2C2E" : "#3A3A3C")
        Text {
            anchors.centerIn: parent
            text: root.letter
            color: "white"
            font.bold: true
            font.pixelSize: Math.max(8, root.height * 0.34)
        }
    }
}
