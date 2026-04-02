import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../Strings.js" as Tr

Button {
    id: captureButton

    // Use RowLayout for better internal alignment
    RowLayout {
        anchors.centerIn: parent

        Image {
            source: "../../assets/camera_icon.png"
            Layout.preferredWidth: 43
            Layout.preferredHeight: 43
            fillMode: Image.PreserveAspectFit
            Layout.alignment: Qt.AlignVCenter
        }

        Text {
            text: Tr.get("captureButton", window.currentLang)
            color: "white"
            font.pixelSize: 15
            font.bold: true
            // Force the text to center vertically in the RowLayout
            Layout.alignment: Qt.AlignVCenter
            
            // This ensures the text box itself doesn't have extra padding
            verticalAlignment: Text.AlignVCenter
        }
    }

    background: Rectangle {
        implicitWidth: 250 
        implicitHeight: 60
        radius: 8
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0078e0" }
            GradientStop { position: 1.0; color: "#008ebe" }
        }
    }

    onClicked: {
        cameraManager.triggerCapture()
    }
}