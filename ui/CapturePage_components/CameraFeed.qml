import QtQuick
import QtQuick.Controls

Rectangle {
    anchors.fill: parent
    color: "black"

    Image {
        id: cameraFeed
        objectName: "cameraFeed"
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        // frameCount change triggers a reload; provider returns the latest frame synchronously
        source: "image://stream/frame?" + mjpegStream.frameCount
        cache: false
        asynchronous: false  // synchronous pull from provider — no blank flash between frames
    }
}
