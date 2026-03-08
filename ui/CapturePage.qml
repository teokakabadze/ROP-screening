import QtQuick
import QtQuick.Controls
import QtMultimedia
import QtQuick.Layouts

Item {
    id: captureRoot
    property bool sideBarOpen: true

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

        // live camera feed and patient data sidebar
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: '#385682'

            RowLayout {
                anchors.fill: parent
                spacing: 2
                
                // camera feed
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: sideBarOpen ? parent.width * 0.7 : parent.width
                    color: 'black'
                    radius: 8

                    VideoOutput {
                        id: cameraFeed
                        objectName: "cameraFeed"
                        anchors.fill: parent
                        fillMode: VideoOutput.PreserveAspectCrop // if we want to maintain the circular eye shape?
                    }

                    // toggle sidebar button
                    Button {
                        id: sideBarToggle
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 10

                        width: 72
                        height: 33
                        
                        onClicked: captureRoot.sideBarOpen = !captureRoot.sideBarOpen

                        contentItem: Text {
                            text: captureRoot.sideBarOpen ? "Hide ➡️" : "Show ⬅"
                            color: "white"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.bold: true
                        }

                        background: Rectangle {
                            color: "#2c3e50"
                            opacity: 0.6 // Slightly see-through so it doesn't block the video
                            radius: 4
                        }
                    }
                }
                // patient data sidebar
                Rectangle {
                    Layout.fillHeight: true
                    Layout.preferredWidth: sideBarOpen ? parent.width * 0.3 : 0
                    color: '#f8f9fa'
                    opacity: sideBarOpen ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 300 } } // check what this does

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 10

                        Text { text: "Patient Name: John Doe"; font.pixelSize: 16 }
                        Text { text: "Age: 2 months"; font.pixelSize: 16 }
                        Text { text: "Gestational Age at Birth: 28 weeks"; font.pixelSize: 16 }
                        Text { text: "Current Weight: 1.5 kg"; font.pixelSize: 16 }
                    }
                }   
            }
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
                color: "white"  
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
    }
}
