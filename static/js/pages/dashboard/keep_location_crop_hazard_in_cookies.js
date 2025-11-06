// key names in storage
const LS_KEY_LOCATION = "lx_selected_location";
const LS_KEY_CROP     = "lx_selected_crop";
const LS_KEY_PATHOGEN = "lx_selected_pathogen";
const LS_KEY_CROP_LABEL     = "lx_selected_crop_label";
const LS_KEY_PATHOGEN_LABEL = "lx_selected_pathogen_label";

// 1) restore on load
document.addEventListener("DOMContentLoaded", function () {
    // location (text input)
    const locInput = document.getElementById("searchAddress");
    const savedLoc = localStorage.getItem(LS_KEY_LOCATION);
    if (locInput && savedLoc) {
        locInput.value = savedLoc;
    }

    // crop (select)
    const cropSelect = document.getElementById("crop_list");
    const savedCrop = localStorage.getItem(LS_KEY_CROP);
    if (cropSelect && savedCrop) {
        cropSelect.value = savedCrop;
    }

    // pathogen (select)
    const pathogenSelect = document.getElementById("pathogen_list");
    const savedPathogen = localStorage.getItem(LS_KEY_PATHOGEN);
    if (pathogenSelect && savedPathogen) {
        pathogenSelect.value = savedPathogen;
    }
});

// 2) save on change
document.addEventListener("change", function (ev) {
    const target = ev.target;

    if (target.id === "searchAddress") {
        // user typed something -> store it
        localStorage.setItem(LS_KEY_LOCATION, target.value);
    }
    if (target.id === "crop_list") {
        // store ID
        localStorage.setItem(LS_KEY_CROP, target.value);

        // store label/text
        const opt = target.options[target.selectedIndex];
        if (opt) {
            localStorage.setItem(LS_KEY_CROP_LABEL, opt.textContent.trim());
        }
    }
    if (target.id === "pathogen_list") {
        // store ID
        localStorage.setItem(LS_KEY_PATHOGEN, target.value);

        // store label/text
        const opt = target.options[target.selectedIndex];
        if (opt) {
            localStorage.setItem(LS_KEY_PATHOGEN_LABEL, opt.textContent.trim());
        }
    }
});

// 3) clear button already exists --> hook it
const clearBtn = document.getElementById("clearSearch");
if (clearBtn) {
    clearBtn.addEventListener("click", function () {
        localStorage.removeItem(LS_KEY_LOCATION);
        const locInput = document.getElementById("searchAddress");
        if (locInput) locInput.value = "";
    });
}

document.getElementById("resetSelections")?.addEventListener("click", function () {
    localStorage.removeItem("lx_selected_location");
    localStorage.removeItem("lx_selected_crop");
    localStorage.removeItem("lx_selected_pathogen");
    localStorage.removeItem("lx_selected_crop_label");
    localStorage.removeItem("lx_selected_pathogen_label");

    // also clear UI
    const loc = document.getElementById("searchAddress");
    const crop = document.getElementById("crop_list");
    const haz  = document.getElementById("pathogen_list");
    if (loc)  loc.value = "";
    if (crop) crop.value = "";
    if (haz)  haz.value  = "";
});