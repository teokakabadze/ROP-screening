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