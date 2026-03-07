import QtQuick
import QtQuick.Controls

Item {
    id: captureRoot

    Rectangle {
        anchors.fill: parent
        color: "#001B2E"

        Text {
            text: "Camera feed will appear here"
            color: "white"
            font.pixelSize: 24
            anchors.centerIn: parent
        }

        Button {
            text: "Capture Image"
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.margins: 40

            onClicked: console.log("Image captured!")   
        }
    }
}
