import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: detailsPage
    // These properties get filled when we push the page
    property string pName: ""
    property string pId: ""

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 30
        spacing: 20

        RowLayout {
            Button { 
                text: "← Back"
                onClicked: stackView.pop() // Goes back to the list
            }
            Text {
                text: "Patient Details: " + pName
                font.pixelSize: 26; font.bold: true
            }
        }

        // Image Gallery Grid
        Text { text: "Captured Images"; font.pixelSize: 18; font.bold: true }
        
        GridView {
            Layout.fillWidth: true; Layout.fillHeight: true
            model: 5 // Placeholder for demo
            cellWidth: 200; cellHeight: 200
            delegate: Rectangle {
                width: 180; height: 180; color: "#f1f5f9"; radius: 10
                Image {
                    anchors.centerIn: parent
                    source: "qrc:/assets/placeholder_retina.png" // Your sample images
                    width: 160; height: 160; fillMode: Image.PreserveAspectFit
                }
            }
        }
    }
}