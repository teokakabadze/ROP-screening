import QtQuick
import QtQuick.Controls
import QtMultimedia

Item {
    id: captureRoot

    VideoOutput {
        id: cameraFeed
        objectName: "cameraFeed"
        anchors.fill: parent
        // fillMode: VideoOutput.PreserveAspectCrop if we want to maintain the circular eye shape

        /* Text {
            text: "Camera feed will appear here"
            color: "black"
            font.pixelSize: 24
            anchors.centerIn: parent
        } */

        Button {
            text: "Capture Image"
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.margins: 40

            onClicked: console.log("Image captured!")   
        }
    }
}
