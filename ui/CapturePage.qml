import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Effects
import "CapturePage_components"
import "Strings.js" as Tr

// deviceManager and cameraManager are set as context properties in main.py

Item {
    id: captureRoot
    objectName: "CapturePage"
    property bool sideBarOpen: true

    // 1. THE BLUE ACTIVE INDICATOR
    // This sits at the very top to meet the toolbar seamlessly
    Rectangle {
        id: activeTabLine
        z: 10
        width: 85
        height: 3
        color: "#0070c0"
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.leftMargin: 56 // Aligns with Toolbar
    }

    // 2. THE MAIN PAGE BACKGROUND
    // Setting this to #f8fafc removes the "black line" gap
    Rectangle {
        anchors.fill: parent
        color: "#f8fafc"

        ColumnLayout {
            anchors.fill: parent
            spacing: 0 // Eliminates gaps between layout elements

            // Main Workspace
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // --- CAMERA FEED SECTION ---
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: sideBarOpen ? parent.width * 0.7 : parent.width

                    // Added margins here so the "Card" looks like it's floating on the gray background
                    Layout.leftMargin: 20
                    Layout.rightMargin: 10
                    Layout.topMargin: 15
                    Layout.bottomMargin: 15

                    radius: 12
                    color: '#ffffff'
                    border.color: '#e2e8f0' // Softer border color for a modern look
                    border.width: 1

                    // Internal Camera Feed Layout
                    Item {
                        anchors.fill: parent
                        anchors.margins: 10

                        CameraFeed {
                            id: liveFeed
                            anchors.fill: parent

                            // Resolution toggle (Top Left)
                            Rectangle {
                                id: modeToggle
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.margins: 10
                                width: 110; height: 34
                                radius: 6
                                color: "#2c3e50"
                                opacity: 0.8

                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 2
                                    spacing: 1

                                    Rectangle {
                                        width: (parent.width / 2) - 1; height: parent.height
                                        radius: 4
                                        color: deviceManager.captureMode === "16mp" ? "white" : "transparent"
                                        Text {
                                            anchors.centerIn: parent
                                            text: "16 MP"; font.pixelSize: 11; font.bold: true
                                            color: deviceManager.captureMode === "16mp" ? "#2c3e50" : "white"
                                        }
                                        MouseArea { anchors.fill: parent; onClicked: deviceManager.setMode("16mp") }
                                    }
                                    Rectangle {
                                        width: (parent.width / 2) - 1; height: parent.height
                                        radius: 4
                                        color: deviceManager.captureMode === "48mp" ? "white" : "transparent"
                                        Text {
                                            anchors.centerIn: parent
                                            text: "64 MP"; font.pixelSize: 11; font.bold: true
                                            color: deviceManager.captureMode === "48mp" ? "#2c3e50" : "white"
                                        }
                                        MouseArea { anchors.fill: parent; onClicked: deviceManager.setMode("48mp") }
                                    }
                                }
                            }

                            // camera state overlay — top-left below mode toggle
                            Rectangle {
                                id: cameraStateOverlay
                                anchors.left: parent.left
                                anchors.top: modeToggle.bottom
                                anchors.leftMargin: 10
                                anchors.topMargin: 6
                                height: 33
                                width: stateRow.width + 20
                                radius: 6
                                color: "#2c3e50"
                                opacity: 0.75

                                property int brightness: 50
                                property string focusText: "AUTO"

                                Connections {
                                    target: deviceManager
                                    function onBrightnessChanged(v) { cameraStateOverlay.brightness = v }
                                    function onFocusChanged(v) { cameraStateOverlay.focusText = v.toFixed(1) }
                                }

                                Row {
                                    id: stateRow
                                    anchors.centerIn: parent
                                    spacing: 14

                                    Row {
                                        spacing: 5
                                        Text {
                                            text: "BRT"
                                            font.pixelSize: 11; font.bold: true
                                            color: "#aaaaaa"
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        TextInput {
                                            id: brtInput
                                            color: "white"
                                            font.pixelSize: 11; font.bold: true
                                            width: 28
                                            selectByMouse: true
                                            validator: IntValidator { bottom: 0; top: 100 }
                                            Binding on text {
                                                when: !brtInput.activeFocus
                                                value: cameraStateOverlay.brightness.toString()
                                            }
                                            onAccepted: {
                                                var v = parseInt(text)
                                                if (!isNaN(v)) deviceManager.setBrightness(v)
                                                focus = false
                                            }
                                        }
                                    }

                                    Row {
                                        spacing: 5
                                        Text {
                                            text: "FOC"
                                            font.pixelSize: 11; font.bold: true
                                            color: "#aaaaaa"
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        TextInput {
                                            id: focInput
                                            color: "white"
                                            font.pixelSize: 11; font.bold: true
                                            width: 38
                                            selectByMouse: true
                                            Binding on text {
                                                when: !focInput.activeFocus
                                                value: cameraStateOverlay.focusText
                                            }
                                            onAccepted: {
                                                var v = parseFloat(text)
                                                if (!isNaN(v)) deviceManager.setFocus(v)
                                                focus = false
                                            }
                                        }
                                    }
                                }
                            }

                            ToggleButton {
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 10
                            }
                        }

                        CaptureButton {
                            id: captureBtn
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom
                            width: parent.width * 0.95
                            height: 40
                            anchors.margins: 5
                        }
                    }
                }

                // --- SIDEBAR SECTION ---
                PatientDataSidebar {
                    Layout.fillHeight: true
                    Layout.preferredWidth: 320
                    visible: sideBarOpen
                }
            }
        }
    }
}
