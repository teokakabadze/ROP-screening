import QtQuick
import QtQuick.Controls
import QtMultimedia
import QtQuick.Layouts

Item {
    id: captureRoot

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // header
        Rectangle {
            Layout.fillWidth: true
            color: "#f8f9fa"
            Layout.preferredHeight: 50 // maybe dont make it fixed in the future

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.rightMargin: 20

                Text {
                    text: "ROP Screening"
                    font.pixelSize: 20
                    color: '#38526b'
                    Layout.alignment: Qt.AlignVCenter
                }
                Item { Layout.fillWidth: true }
                Row {
                    spacing: 8
                    Layout.alignment: Qt.AlignVCenter
                    Rectangle {
                        width: 12; height: 12; radius: 6
                        color: "#27ae60"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text { text: "Live"; font.bold: true; color: "#27ae60"}
                }
            }
        }

        // live camera feed
        Rectangle {
            color: "#222"
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        // capture button
        Button {
            id: captureButton
            Layout.fillWidth: true
            Layout.preferredHeight: 50
            Layout.leftMargin: 20
            Layout.rightMargin: 20

            Text {
                text: "📷  Capture Image"  
                font.pixelSize: 20         
                anchors.centerIn: parent    
            }

            background: Rectangle {
                implicitWidth: 100; implicitHeight: 60
                radius: 8
                
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#007bff" }
                    GradientStop { position: 1.0; color: "#00a8cc" }
                }
            }
            opacity: captureButton.pressed ? 0.8 : 1.0
        }
        /* VideoOutput {
            id: cameraFeed
            objectName: "cameraFeed"
            anchors.fill: parent
            // fillMode: VideoOutput.PreserveAspectCrop if we want to maintain the circular eye shape
        } */
    }
}
