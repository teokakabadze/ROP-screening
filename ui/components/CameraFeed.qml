import QtMultimedia

VideoOutput {
    id: cameraFeed
    objectName: "cameraFeed"
    anchors.fill: parent
    fillMode: VideoOutput.PreserveAspectCrop // if we want to maintain the circular eye shape?
}