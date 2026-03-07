import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window
    visible: true
    width: 800; height: 480
    title: "ROP screening"

    CapturePage {
        anchors.fill: parent
    }
}
