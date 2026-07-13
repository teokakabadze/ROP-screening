var data = {
    "EN": {
        "appTitle": "Retinex",
        "appSubtitle": "Retinopathy of Prematurity Detection",
        "captureButton": "Capture Image",
        "hideButton": "Hide →",
        "showButton": "Show ←",
        "patientinfo": "Patient Information",
        "patientID": "Patient ID",
        "patientName": "Name",
        "age": "Gestational Age",
        "weight": "Birth Weight",
        "screeningDate": "Screening Date",
        "recentCaptures": "Recent Captures",
        "noCaptures": "No images captured yet",
        "week": "weeks",
        "patients": "Patients",
        "capture": "Capture",
    },
    "SW": {
        "appTitle": "Retinex",
        "appSubtitle": "Ugonjwa wa Retina kwa Watoto Njiti",
        "captureButton": "Piga Picha",
        "hideButton": "Ficha →",
        "showButton": "Angalia ←",
        "patientinfo": "Taarifa za Mgonjwa",
        "patientID": "Namba ya Mgonjwa",
        "patientName": "Jina",
        "age": "Umri wa Ujauzito",
        "weight": "Uzito wa Kuzaliwa",
        "screeningDate": "Tarehe ya Upimaji",
        "recentCaptures": "Picha Zilizopigwa Hivi Karibuni",
        "noCaptures": "Hakuna picha zilizopigwa bado",
        "week": "wiki",
        "patients": "Wagonjwa",
        "capture": "Piga",
    }
}

function get(key, lang) {
    return data[lang][key] || data["EN"][key]; // fallback to English if key or language is missing
}