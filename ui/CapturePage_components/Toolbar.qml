import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../Strings.js" as Tr

ToolBar {
    id: navigationBar
    width: parent.width
    // slightly higher
    height: 45
    
    background: Rectangle {
        color: "white" // Match the main header background
        
        // Bottom border for separation from the page content
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: "#eeeeee"
        }
    }

    Row {
        spacing: 30 // Increased spacing for a breathable, modern feel
        anchors.left: parent.left
        anchors.leftMargin: 56 // Align with the Logo above
        anchors.verticalCenter: parent.verticalCenter

        // --- CAPTURE BUTTON ---
        Button {
            id: captureBtn
            text: Tr.get("capture", window.currentLang)
            flat: true
            
            contentItem: Text {
                text: captureBtn.text
                font.pixelSize: 16
                font.bold: stackView.currentItem && stackView.currentItem.objectName === "CapturePage"
                color: font.bold ? "#0070c0" : "#7f8c8d" // Blue if active, grey if not
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            // Optional: Underline for the active tab
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.bottomMargin: -5
                width: parent.width
                height: 3
                color: "#0070c0"
                visible: stackView.currentItem && stackView.currentItem.objectName === "CapturePage"
            }

            onClicked: {
                stackView.replace("../CapturePage.qml")
            }
        }

        // --- PATIENTS BUTTON ---
        Button {
            id: patientsBtn
            text: Tr.get("patients", window.currentLang)
            flat: true
            
            contentItem: Text {
                text: patientsBtn.text
                font.pixelSize: 16
                font.bold: stackView.currentItem && stackView.currentItem.objectName === "PatientListPage"
                color: font.bold ? "#0070c0" : "#7f8c8d"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.bottomMargin: -5
                width: parent.width
                height: 3
                color: "#0070c0"
                visible: stackView.currentItem && stackView.currentItem.objectName === "PatientListPage"
            }

            onClicked: stackView.replace("../PatientListPage.qml")
        }
    }
}