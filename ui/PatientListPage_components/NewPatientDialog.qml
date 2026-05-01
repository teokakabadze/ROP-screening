import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: addPatientDialog
    modal: true
    standardButtons: Dialog.NoButton
    anchors.centerIn: Overlay.overlay
    
    // 1. PROFESSIONAL BACKGROUND
    background: Rectangle {
        implicitWidth: 460
        radius: 16 // More rounded for a modern medical feel
        color: "#ffffff"
        
        // Subtle drop shadow effect using a border
        border.color: "#e2e8f0"
        border.width: 1
    }

    contentItem: ColumnLayout {
        spacing: 24 // Increased spacing for a breathable layout
        
        Text {
            text: "Add New Patient Details"
            font.pixelSize: 22
            font.weight: Font.Bold
            color: "#0f172a" // Deep Navy/Black
            Layout.topMargin: 10
        }

        // 2. REFINED INPUT COMPONENT
        component CustomInput : ColumnLayout {
            property alias label: lbl.text
            property alias placeholder: field.placeholderText
            property alias text: field.text
            spacing: 8
            Layout.fillWidth: true
            
            Text { 
                id: lbl
                font.pixelSize: 13
                font.weight: Font.Medium
                color: "#64748b" // Professional Slate Gray
            }
            
            TextField {
                id: field
                Layout.fillWidth: true
                Layout.preferredHeight: 42
                leftPadding: 12
                color: "#1e293b"
                font.pixelSize: 15
                placeholderTextColor: "#94a3b8"
                
                background: Rectangle {
                    radius: 8
                    color: field.activeFocus ? "#ffffff" : "#f8fafc"
                    border.color: field.activeFocus ? "#0070c0" : "#e2e8f0"
                    border.width: field.activeFocus ? 2 : 1
                    
                    // Smooth transition for focus
                    Behavior on border.color { ColorAnimation { duration: 150 } }
                }
            }
        }

        CustomInput { id: idIn; label: "Patient ID"; placeholder: "e.g. ROP-001" }
        CustomInput { id: nameIn; label: "Full Name"; placeholder: "Enter patient's name" }
        
        RowLayout {
            spacing: 20
            CustomInput { id: gestIn; label: "Gestation (weeks)"; placeholder: "28" }
            CustomInput { id: weightIn; label: "Birth Weight (g)"; placeholder: "1200" }
        }

        // 3. CUSTOM PROFESSIONAL BUTTONS
        RowLayout {
            Layout.alignment: Qt.AlignRight
            Layout.topMargin: 10
            spacing: 12

            Button {
                id: cancelBtn
                text: "Cancel"
                flat: true
                contentItem: Text {
                    text: cancelBtn.text
                    color: "#64748b"
                    font.pixelSize: 15
                    font.weight: Font.Medium
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: addPatientDialog.close()
            }

            Button {
                id: saveBtn
                text: "Save Patient"
                Layout.preferredWidth: 140
                Layout.preferredHeight: 45
                
                contentItem: Text {
                    text: saveBtn.text
                    color: "white"
                    font.pixelSize: 15
                    font.weight: Font.Bold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    radius: 8
                    // Matches the "New Patient" button blue
                    color: saveBtn.pressed ? "#005a9e" : (saveBtn.hovered ? "#0078d4" : "#0070c0")
                }
                
                onClicked: {
                    let currentDate = new Date();
                    let dateString = currentDate.toLocaleDateString("en-US", {
                        year: 'numeric', month: '2-digit', day: '2-digit'
                    });
                    
                    patientModel.append({
                        "patientId": idIn.text,
                        "name": nameIn.text,
                        "gestation": gestIn.text + " weeks",
                        "weight": weightIn.text + "g",
                        "date": dateString,
                        "imageCount": 0
                    })
                    addPatientDialog.close()
                }
            }
        }
    }
}