import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// A small card in the corner that says a newer Hearth exists. Not modal.
Rectangle {
    id: notice

    property string version: ""
    property string current: ""
    property bool shown: false
    signal download()
    signal later()
    signal skip()

    objectName: "updateNotice"
    visible: opacity > 0
    opacity: shown ? 1 : 0
    width: 320
    height: column.implicitHeight + 32
    radius: 14
    color: "#16161A"
    border.color: "#3A3A40"
    border.width: 1

    Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

    MouseArea { anchors.fill: parent }

    ColumnLayout {
        id: column
        x: 16
        y: 16
        width: parent.width - 32
        spacing: 6

        Text {
            objectName: "updateTitle"
            Layout.fillWidth: true
            text: "Hearth " + notice.version + " is available"
            color: "white"
            font.pixelSize: 15
            font.bold: true
            wrapMode: Text.WordWrap
        }
        Text {
            Layout.fillWidth: true
            text: notice.current !== "" ? "You have " + notice.current + "." : ""
            visible: text !== ""
            color: "#8E8E93"
            font.pixelSize: 12
        }
        RowLayout {
            Layout.topMargin: 8
            spacing: 8
            Button {
                objectName: "updateDownload"
                text: "Open download page"
                onClicked: notice.download()
                background: Rectangle { radius: 8; color: parent.down ? "#0A6FD6" : "#0A84FF" }
                contentItem: Text { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.bold: true; leftPadding: 12; rightPadding: 12 }
            }
            Button {
                objectName: "updateLater"
                text: "Not now"
                onClicked: notice.later()
                background: Rectangle { radius: 8; color: "transparent"; border.color: "#3A3A40"; border.width: 1 }
                contentItem: Text { text: parent.text; color: "#C7C7CC"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; leftPadding: 12; rightPadding: 12 }
            }
        }
        Text {
            objectName: "updateSkip"
            text: "Skip this version"
            color: "#8E8E93"
            font.pixelSize: 11
            font.underline: skipArea.containsMouse
            MouseArea {
                id: skipArea
                anchors.fill: parent
                anchors.margins: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: notice.skip()
            }
        }
    }
}
