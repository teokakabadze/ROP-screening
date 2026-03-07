import QtQuick
import QtQuick.Controls

Item {
    id: captureRoot

    Rectangle {
        anchors.fill: parent
        color: "#001B2E" // Dark Blue background

        Text {
            text: "CAPTURE SCREEN"
            color: "white"
            font.pixelSize: 24
            anchors.centerIn: parent
        }

        Button {
            text: "TAKE PHOTO"
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.margins: 40

            onClicked: console.log("Capture triggered!")
        }
    }
}
