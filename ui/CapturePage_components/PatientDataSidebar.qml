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

                    DataField { label: "patientID"; value: "ROP-DEMO-001"; valueColor: "#007bff" }
                    DataField { label: "patientName"; value: "John Doe" }
                    DataField { label: "age"; value: "28 " + Tr.get("week", window.currentLang) }
                    DataField { label: "weight"; value: "1500 g" }
                    DataField { label: "screeningDate"; value: "3/10/2026" }
                }
            }
        }

        // Image Gallery
        ColumnLayout {
            Layout.fillHeight: true 
            spacing: 8

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
                    model: 0 

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