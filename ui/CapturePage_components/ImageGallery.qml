import QtQuick
import QtQuick.Layouts
import "../Strings.js" as Tr

ColumnLayout {
    Layout.fillHeight: true 
    spacing: 8

    Connections {
        target: cameraManager
        function onImageSaved(path) {
            console.log("adding to gallery:", path)
            galleryModel.insert(0, { "filesource": path })
        }
    }

    Text {
        text: Tr.get("recentCaptures", window.currentLang)
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        font.bold: true
        font.pixelSize: 16
        color: "#2c3e50"
    }

    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        color: "#f8f9fa"
        radius: 12
        border.color: "#eeeeee"
        border.width: 1
        clip: true

        GridView {
            id: galleryGrid
            anchors.fill: parent
            anchors.margins: 10
            cellWidth: parent.width / 2
            cellHeight: 110

            model: ListModel { id: galleryModel }

            delegate: Item {
                width: galleryGrid.cellWidth
                height: galleryGrid.cellHeight

                Rectangle {
                    anchors.fill: parent 
                    anchors.margins: 4
                    radius: 8
                    color: "white"
                    border.color: "#dddddd"
                    clip:true

                    Image {
                        anchors.fill: parent 
                        source: model.fileSource
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                text: Tr.get("noCaptures", window.currentLang)
                color: "#bdc3c7"
                font.italic: true
                visible: galleryGrid.count === 0
            }
        }
    }
}