import QtQuick
import QtQuick.Layouts

Rectangle {
    id: headerRoot
    color: "#f8f9fa"
    implicitHeight: 50

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