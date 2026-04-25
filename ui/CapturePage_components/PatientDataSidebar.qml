import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../Strings.js" as Tr

Rectangle {
    id: sideBarRoot
    Layout.fillHeight: true
    Layout.preferredWidth: sideBarOpen ? parent.width * 0.3 : 0
    color: '#ffffff'
    clip: true

    Behavior on Layout.preferredWidth { NumberAnimation { duration: 250; easing.type: Easing.InOutQuad } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 13
        spacing: 20

        // --- SECTION 1: Patient Data ---
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            // Clean Title Row
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: Tr.get("patientinfo", window.currentLang)
                    font.bold: true
                    font.pixelSize: 16
                    color: "#2c3e50"
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 240
                color: "#fcfdfe"
                radius: 12
                border.color: "#dbefff"
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 15
                    spacing: 12

                    DataField { 
                        label: "patientID"
                        // If activePatient exists, show the ID. Otherwise, show "N/A"
                        value: activePatient ? activePatient.patientId : "---" 
                        valueColor: "#007bff" 
                    }
                    DataField { 
                        label: "patientName"
                        value: activePatient ? activePatient.name : "Select Patient" 
                    }
                    DataField { 
                        label: "age"
                        value: activePatient ? activePatient.gestation : "---" 
                    }
                    DataField { 
                        label: "weight"
                        value: activePatient ? activePatient.weight : "---" 
                    }
                    DataField { 
                        label: "screeningDate"
                        value: activePatient ? activePatient.date : "---" 
                    }
                }
            }
        }

        // Image Gallery
        ColumnLayout {
            Layout.fillHeight: true
            spacing: 8

            ListModel { id: captureModel }

            Connections {
                target: cameraManager
                function onImageSaved(url) { captureModel.insert(0, { imageUrl: url }) }
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
                    model: captureModel

                    delegate: Rectangle {
                        width: galleryGrid.cellWidth - 6
                        height: galleryGrid.cellHeight - 6
                        radius: 6
                        color: "#e8f4fd"
                        clip: true

                        Image {
                            anchors.fill: parent
                            anchors.margins: 3
                            source: imageUrl
                            fillMode: Image.PreserveAspectCrop
                            smooth: true
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
    }
}