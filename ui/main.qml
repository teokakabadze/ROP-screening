import QtQuick
import QtQuick.Controls
import "Strings.js" as Tr
import "./CapturePage_components" as Components

ApplicationWindow {
    id: window
    visible: true
    width: 1024; height: 600 // Increased size to match your reference image
    title: "ROP Screening"

    // captureheader is the top bar with the logo and title
    header: Column {
        // 1. Your custom branding/logo bar
        Components.CaptureHeader { 
            id: appHeader 
            width: parent.width // Ensure it spans full width
        }

        // 2. Your navigation toolbar
        Components.Toolbar {
            id: navBar
            width: parent.width // Ensure it spans full width
        }
    }
    property string currentLang: "EN"

    property var activePatient: null 

    // Optional: A helper function to set the patient
    function selectPatient(patientData) {
        activePatient = patientData;
        stackView.push("CapturePage.qml"); // Automatically jump to camera
    }

    // 1. DATA MODEL: This holds all our patients globally
    ListModel {
        id: patientModel
        ListElement { 
            patientId: "ROP-DEMO-001"; name: "Demo Patient"; 
            gestation: "28 weeks"; weight: "1200g"; 
            date: "4/23/2026"; imageCount: 0 
        }
    }

    // 3. THE STACK: This manages which page is visible
    StackView {
        id: stackView
        anchors.fill: parent
        initialItem: "PatientListPage.qml" // Start on the list
    }
}