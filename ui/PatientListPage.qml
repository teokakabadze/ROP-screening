// PatientListPage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "./PatientListPage_components"

Item {
    id: root
    objectName: "PatientListPage"

    Rectangle {
        anchors.fill: parent
        color: "#f8fafc" 
    }

    NewPatientDialog { id: patientPopup }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 40
        anchors.rightMargin: 40
        anchors.topMargin: 25   // Reduced to 5 to hug the toolbar
        anchors.bottomMargin: 20
        spacing: 15 

        // --- HEADER SECTION ---
        RowLayout {
            Layout.fillWidth: true
            
            Column {
                spacing: 1
                Text {
                    text: "Patient List"
                    font.pixelSize: 26; font.bold: true
                    color: "#0f172a"
                }
                Text {
                    text: "Manage and view patient screening records"
                    font.pixelSize: 13; color: "#64748b"
                }
            }

            Item { Layout.fillWidth: true } 
            
            // Clean, Professional "New Patient" Button
            Button {
                id: newPatientBtn
                implicitWidth: 120 
                implicitHeight: 34 // Shorter height as requested
                onClicked: patientPopup.open()
                
                background: Rectangle {
                    color: "#0070c0" // Solid professional blue
                    radius: 6
                }

                // Using Item + Row for guaranteed vertical and horizontal centering
                contentItem: Item {
                    Row {
                        anchors.centerIn: parent // This centers the whole group perfectly
                        spacing: 8
                        Text { 
                            text: "+" 
                            color: "white"
                            font.pixelSize: 20 // Slightly larger + looks better aligned
                            font.bold: true 
                            verticalAlignment: Text.AlignVCenter
                        }
                        Text { 
                            text: "New Patient" 
                            color: "white"
                            font.bold: true
                            font.pixelSize: 13
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }
        }

        // --- TABLE CONTAINER (CARD) ---
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "white"
            radius: 10
            border.color: "#e2e8f0"
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // STATIC TABLE HEADER
                Rectangle {
                    Layout.fillWidth: true
                    height: 45
                    color: "#f1f5f9" 
                    radius: 10 
                    
                    Rectangle { 
                        anchors.bottom: parent.bottom; width: parent.width; height: 10; color: parent.color 
                    }

                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 20
                        Text { text: "Patient ID"; Layout.preferredWidth: 140; font.bold: true; color: "#475569"; font.pixelSize: 13 }
                        Text { text: "Name"; Layout.preferredWidth: 160; font.bold: true; color: "#475569"; font.pixelSize: 13 }
                        Text { text: "Gestational Age"; Layout.preferredWidth: 140; font.bold: true; color: "#475569"; font.pixelSize: 13 }
                        Text { text: "Birth Weight"; Layout.preferredWidth: 120; font.bold: true; color: "#475569"; font.pixelSize: 13 }
                        Text { text: "Screening Date"; Layout.preferredWidth: 140; font.bold: true; color: "#475569"; font.pixelSize: 13 }
                        Text { text: "Images"; Layout.preferredWidth: 80; font.bold: true; color: "#475569"; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter }
                        Item { Layout.fillWidth: true }
                        Text { text: "Actions"; Layout.preferredWidth: 170; font.bold: true; color: "#475569"; font.pixelSize: 13; horizontalAlignment: Text.AlignRight }
                    }
                }

                // DATA LIST
                ListView {
                    id: listView
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: patientModel
                    clip: true
                    
                    delegate: Item {
                        width: listView.width
                        height: 60 // Slightly shorter rows for professional density

                        Rectangle {
                            anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#f1f5f9"
                        }

                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 20
                            
                            Text { 
                                text: model.patientId; Layout.preferredWidth: 140
                                color: "#2563eb"; font.pixelSize: 15; font.bold: true 
                            }
                            Text { 
                                text: model.name; Layout.preferredWidth: 160
                                color: "#1e293b"; font.pixelSize: 15; font.bold: true 
                            }
                            Text { text: model.gestation; Layout.preferredWidth: 140; color: "#475569"; font.pixelSize: 15 }
                            Text { text: model.weight; Layout.preferredWidth: 120; color: "#475569"; font.pixelSize: 15 }
                            Text { text: model.date; Layout.preferredWidth: 140; color: "#475569"; font.pixelSize: 15 }

                            Text {
                                text: model.imageCount; Layout.preferredWidth: 80
                                horizontalAlignment: Text.AlignHCenter
                                color: "#1e293b"; font.pixelSize: 15; font.bold: true
                            }

                            Item { Layout.fillWidth: true } 

                            // ACTION BUTTONS
                            RowLayout {
                                spacing: 10
                                Layout.preferredWidth: 170
                                
                                Button {
                                    id: viewBtn
                                    text: "View"
                                    implicitWidth: 75; implicitHeight: 30
                                    background: Rectangle { color: "white"; border.color: "#e2e8f0"; radius: 6 }
                                    contentItem: Text {
                                        text: viewBtn.text; color: "#1e293b"; font.pixelSize: 13; font.bold: true
                                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                    }
                                    onClicked: {
                                        window.activePatient = {
                                            "patientId": model.patientId, "name": model.name,
                                            "gestation": model.gestation, "weight": model.weight, "date": model.date
                                        }
                                        stackView.push("CapturePage.qml")
                                    }
                                }

                                Button {
                                    id: exportBtn
                                    text: "Export"
                                    implicitWidth: 75; implicitHeight: 30
                                    background: Rectangle { color: "white"; border.color: "#e2e8f0"; radius: 6 }
                                    contentItem: Text {
                                        text: exportBtn.text; color: "#475569"; font.pixelSize: 13; font.bold: true
                                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}