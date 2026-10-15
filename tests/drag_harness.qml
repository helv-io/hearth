import QtQuick
import "../hearth/qml"

Item {
    width: 400
    height: 300

    Rectangle {
        id: icon
        objectName: "icon"
        x: 30
        y: 40
        width: 83
        height: 47
        color: "#0A84FF"

        DragSpot {
            anchors.fill: parent
            sample: icon
            source: "page:0:0"
            letter: "A"
            ident: "com.example.a"
            kind: "app"
            dragApi: api
        }
    }

    Item {
        id: dockSlot
        x: 180
        y: 40
        width: 90
        height: 70

        Rectangle {
            id: dockIcon
            objectName: "dockIcon"
            anchors.centerIn: parent
            width: 30
            height: 30
            color: "#3A3A3C"
        }

        DragSpot {
            anchors.fill: parent
            sample: dockIcon
            source: "dock:0"
            letter: "D"
            ident: "com.example.dock"
            kind: "app"
            dragApi: api
        }
    }
}
