import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

Item {
    id: captureRoot
    property bool sideBarOpen: true

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        CaptureHeader { 
            Layout.fillWidth: true
            Layout.preferredHeight: 50
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

                    CameraFeed { }

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
                            opacity: 0.6 
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
                        spacing: 20

                        // switch between patient data and image gallery
                        RowLayout {
                            spacing: 10
                            Button {
                                id: patientDataBtn
                                text: "Patient Data"
                                checkable: true
                                checked: true
                            }
                            Button {
                                id: imageGalleryBtn
                                text: "Image Gallery"
                                checkable: true
                            }
                        }
                
                        // patient data card
                        Rectangle {
                            id: dataCard
                            Layout.fillWidth: true
                            Layout.preferredHeight: 200

                            color: "#edfbff"
                            border.color: '#4a98cd'
                            border.width: 2
                            radius: 12

                            GridLayout {
                                columns: 2
                                anchors.fill: parent
                                anchors.margins: 20
                                rowSpacing: 20
                                columnSpacing: 40

                                Column {
                                    Text { text: "Patient ID"; color: "#7f8c8d"; font.pixelSize: 12 }
                                    Text { text: "ROP-DEMO-001"; color: "#0056b3"; font.bold: true; font.pixelSize: 16 }
                                }
                                Column {
                                    Text { text: "Name"; color: "#7f8c8d"; font.pixelSize: 12 }
                                    Text { text: "John Doe"; color: "#2c3e50"; font.bold: true; font.pixelSize: 16 }
                                }

                                Column {
                                    Text { text: "Gestational Age"; color: "#7f8c8d"; font.pixelSize: 12 }
                                    Text { text: "28 weeks"; color: "#2c3e50"; font.bold: true; font.pixelSize: 16 }
                                }
                                Column {
                                    Text { text: "Birth Weight"; color: "#7f8c8d"; font.pixelSize: 12 }
                                    Text { text: "1500 g"; color: "#2c3e50"; font.bold: true; font.pixelSize: 16 }
                                }
                                
                                Column {
                                    Text { text: "Screening Date"; color: "#7f8c8d"; font.pixelSize: 12 }
                                    Text { text: "3/9/2026"; color: "#2c3e50"; font.bold: true; font.pixelSize: 16 }
                                }
                                Column {
                                    Text { text: "Images Captured"; color: "#7f8c8d"; font.pixelSize: 12 }
                                    Text { text: "0"; color: "#0056b3"; font.bold: true; font.pixelSize: 16 }
                                }
                            } 
                        }
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
