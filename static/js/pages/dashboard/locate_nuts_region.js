$(document).ready(function () {
    // Initialize the map centered on Europe
    var map = L.map('farms_by_locations').setView([50, 10], 4);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    // Add drawing functionality
    var drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);

    var drawControl = new L.Control.Draw({
        edit: {
            featureGroup: drawnItems
        },
        draw: {
            polygon: true,
            polyline: false,
            rectangle: true,
            circle: true,
            marker: true
        }
    });
    map.addControl(drawControl);

    // Handle drawing events
    map.on(L.Draw.Event.CREATED, function (event) {
        var layer = event.layer;
        drawnItems.addLayer(layer);

        // Convert to GeoJSON for backend processing
        var geojson = layer.toGeoJSON();
        console.log("Selected Area:", geojson);

        // Extract coordinates based on geometry type
        var coords;
        if (geojson.geometry.type === "Polygon") {
            coords = geojson.geometry.coordinates[0]; // First ring of the polygon
        } else if (geojson.geometry.type === "Point") {
            coords = [geojson.geometry.coordinates]; // Single point
        } else if (geojson.geometry.type === "Rectangle") {
            coords = geojson.geometry.coordinates[0]; // Rectangles are polygons
        } else {
            return; // Skip unsupported types
        }

        // Format and append to the textarea
        var coordTextArea = $("#selectedCoordinates");
        var existingText = coordTextArea.val();
        var newEntry = JSON.stringify(coords);

        if (existingText) {
            coordTextArea.val(existingText + "\n" + newEntry);
        } else {
            coordTextArea.val(newEntry);
        }
    });

    // "Locate Me" functionality
    $("#locateMe").click(function () {
        if (!navigator.geolocation) {
            alert("Geolocation is not supported by your browser.");
            return;
        }

        navigator.geolocation.getCurrentPosition(
            function (position) {
                var lat = position.coords.latitude;
                var lon = position.coords.longitude;

                // Remove previous marker if it exists
                if (window.searchMarker) {
                    map.removeLayer(window.searchMarker);
                }

                // Add marker for user location
                window.searchMarker = L.marker([lat, lon]).addTo(map)
                    .bindPopup("You are here!").openPopup();

                // Zoom to user location
                map.setView([lat, lon], 10);

                // Fetch and highlight NUTS2 region
                fetchNUTSRegions(lat, lon);
            },
            function () {
                alert("Unable to retrieve your location.");
            }
        );
    });

    var nutsLayer = L.geoJSON(null, {
        style: function () {
            return { color: "blue", weight: 2, fillOpacity: 0.3 };
        }
    }).addTo(map);

    function searchLocation() {
        const query = $("#searchAddress").val().trim();
        if (!query) {
            alert("Please enter a location.");
            return;
        }

        // Try to parse as coordinates (flexible; will infer order & support DMS/hemispheres)
        const parsed = parseCoordinateInput(query);
        if (!parsed.error) {
            flyToCoordinates(parsed.lat, parsed.lon, "Selected coordinates");
            return; // Skip Nominatim
        }

        // Fallback: treat as text → Nominatim
        $("#searchButton").prop("disabled", true).text("Searching...");
        $("#loadingMessage").show();

        const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&addressdetails=1`;

        $.getJSON(url, function (data) {
            if (data.length === 0) {
                alert("Location not found. Try another search.");
                resetSearchButton();
                return;
            }

            $("#locationResults").empty().show();

            data.forEach((location) => {
                $("#locationResults").append(`
                    <li class="list-group-item location-option" data-lat="${location.lat}" data-lon="${location.lon}">
                        ${location.display_name}
                    </li>
                `);
            });

            resetSearchButton();
        }).fail(function () {
            alert("Error retrieving location data.");
            resetSearchButton();
        });
    }

    // Event listener for selecting a location
    $(document).on("click", ".location-option", function () {
        var lat = $(this).data("lat");
        var lon = $(this).data("lon");
        var displayName = $(this).text();

        // Hide the list after selection
        $("#locationResults").hide();

        // Zoom to the selected location
        map.setView([lat, lon], 10);

        // Add a marker at the selected location
        if (window.searchMarker) {
            map.removeLayer(window.searchMarker);
        }
        window.searchMarker = L.marker([lat, lon]).addTo(map)
            .bindPopup(displayName).openPopup();

        // Fetch and highlight the NUTS2 region
        fetchNUTSRegions(lat, lon);
    });

    // Global variable to store the selected region layer
    var selectedRegionLayer = null;

    // Jump to numeric coordinates and fetch NUTS2
    function flyToCoordinates(lat, lon, label = null) {
        const latNum = parseFloat(lat), lonNum = parseFloat(lon);
        if (!isFinite(latNum) || !isFinite(lonNum) || latNum < -90 || latNum > 90 || lonNum < -180 || lonNum > 180) {
            alert("Invalid latitude/longitude.");
            return;
        }

        if (window.searchMarker) map.removeLayer(window.searchMarker);

        window.searchMarker = L.marker([latNum, lonNum]).addTo(map)
            .bindPopup(label || `Lat: ${latNum.toFixed(5)}, Lon: ${lonNum.toFixed(5)}`).openPopup();

        map.setView([latNum, lonNum], 10);
        fetchNUTSRegions(latNum, lonNum);
    }

    function fetchNUTSRegions(lat, lon) {
        var nutsUrl = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_01M_2021_4326_LEVL_2.geojson";

        $.getJSON(nutsUrl, function (geojsonData) {
            nutsLayer.clearLayers();
            nutsLayer.addData(geojsonData);

            // Style all NUTS2 regions in blue
            nutsLayer.setStyle({
                color: "blue",
                weight: 2,
                fillOpacity: 0.3
            });

            // Find the selected region
            var selectedRegion = geojsonData.features.find(feature => {
                let geometry = feature.geometry;
                let coords = geometry.coordinates;

                if (geometry.type === "MultiPolygon") {
                    return coords.some(polygon => {
                        return polygon.some(ring => {
                            if (ring.length < 4) return false;
                            return turf.booleanPointInPolygon(
                                turf.point([lon, lat]),
                                turf.polygon([ring])
                            );
                        });
                    });
                } else if (geometry.type === "Polygon") {
                    return coords.some(ring => {
                        if (ring.length < 4) return false;
                        return turf.booleanPointInPolygon(
                            turf.point([lon, lat]),
                            turf.polygon([ring])
                        );
                    });
                }
                return false;
            });

            if (selectedRegion) {
                console.log("Selected NUTS2 Region ID:", selectedRegion.properties.NUTS_ID);
                console.log("All Available Properties:");
                console.table(selectedRegion.properties); // This gives a nice formatted table in browser console

                console.log("Geometry Type:", selectedRegion.geometry.type);
                console.log("Coordinates:", selectedRegion.geometry.coordinates);


                // Remove the previous selected region if it exists
                if (selectedRegionLayer) {
                    map.removeLayer(selectedRegionLayer);
                }

                // Highlight the selected NUTS2 region in green
                selectedRegionLayer = L.geoJSON(selectedRegion, {
                    style: {
                        color: "green",
                        weight: 3,
                        fillOpacity: 0.5
                    }
                }).addTo(map);

                // Fit map to selected region
                map.fitBounds(selectedRegionLayer.getBounds());
            } else {
                alert("No NUTS2 region found for this location.");
            }
        }).fail(function () {
            alert("Error loading NUTS regions.");
        });
    }


    function resetSearchButton() {
        $("#searchButton").prop("disabled", false).text("🔍 Search");
        $("#loadingMessage").hide();
    }

    $("#searchButton").click(searchLocation);

    $("#locationForm").on("submit", function (e) {
        e.preventDefault();          // stop the browser submitting the form
        searchLocation();
    });

    $("#coordsHelp").on("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            $(this).trigger("click"); // opens the modal (data-bs-* handles it)
        }
    });

    // Clear search input, results, and any map highlights/markers
    $("#clearSearch").on("click", function () {
        // 1) Text input + results UI
        $("#searchAddress").val("");                  // clear the input
        $("#locationResults").empty().hide();               // clear & hide the results list
        $("#loadingMessage").hide();                        // hide "Please wait..."
        resetSearchButton();                                // re-enable the Search button text/state

        // 2) Map clean-up
        if (window.searchMarker) {                          // remove the last search marker
            map.removeLayer(window.searchMarker);
            window.searchMarker = null;
        }
        if (selectedRegionLayer) {                          // remove highlighted NUTS2 polygon
            map.removeLayer(selectedRegionLayer);
            selectedRegionLayer = null;
        }

        // 3) Also clear drawn shapes & the textarea that stores drawn coords
        drawnItems.clearLayers();
        $("#selectedCoordinates").val("");
    });
});


function dmsToDecimal(d, m = 0, s = 0) {
    const sign = d < 0 ? -1 : 1;
    return sign * (Math.abs(d) + (m || 0) / 60 + (s || 0) / 3600);
}

function parseCoordToken(tok) {
    // Normalise token
    let t = tok.trim()
        .replace(/[°º]/g, "°")
        .replace(/[′’]/g, "'")
        .replace(/[″”]/g, '"')
        .replace(/\s+/g, " ");

    // Extract hemisphere (if any)
    let hemi = null;
    const hemiMatch = t.match(/([NSEW])/i);
    if (hemiMatch) hemi = hemiMatch[1].toUpperCase();

    // DMS pattern: 12°34'56.78"
    let dms = t.match(/(-?\d+(?:\.\d+)?)\s*°\s*(\d+(?:\.\d+)?)?\s*'?\s*(\d+(?:\.\d+)?)?\s*"?/);
    if (dms) {
        let deg = parseFloat(dms[1]);
        let min = dms[2] !== undefined ? parseFloat(dms[2]) : 0;
        let sec = dms[3] !== undefined ? parseFloat(dms[3]) : 0;
        let val = dmsToDecimal(deg, min, sec);
        return { value: val, hemi };
    }

    // Space-separated DMS: 12 34 56.78
    let dmsSpace = t.match(/^\s*(-?\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*([NSEW])?\s*$/i);
    if (dmsSpace) {
        let deg = parseFloat(dmsSpace[1]);
        let min = parseFloat(dmsSpace[2]);
        let sec = parseFloat(dmsSpace[3]);
        let val = dmsToDecimal(deg, min, sec);
        return { value: val, hemi: (dmsSpace[4] || hemi || "").toUpperCase() || null };
    }

    // Decimal degrees
    // Accept dot decimals; allow leading hemi (N50.1) or trailing (50.1N)
    let dec = t.match(/^[NSEW]?\s*(-?\d+(?:\.\d+)?)\s*[NSEW]?$/i);
    if (dec) {
        let val = parseFloat(dec[1]);
        // If hemisphere attached, use that
        if (!hemi) {
            const head = t.trim().charAt(0).toUpperCase();
            const tail = t.trim().slice(-1).toUpperCase();
            if ("NSEW".includes(head)) hemi = head;
            else if ("NSEW".includes(tail)) hemi = tail;
        }
        return { value: val, hemi };
    }

    // European decimal comma support if token itself contains one (we'll convert)
    if (/^-?\d+,\d+$/.test(t)) {
        let val = parseFloat(t.replace(",", "."));
        return { value: val, hemi };
    }

    return { error: "Unrecognised coordinate token: " + tok };
}

function normalisePairSeparator(s) {
    // Prefer splitting on comma or semicolon first; else collapse multiple spaces
    if (s.includes(";")) return s.split(";").map(x => x.trim());
    if (s.includes(",")) return s.split(",").map(x => x.trim());
    // If many spaces, split on whitespace but only into two parts
    const parts = s.trim().split(/\s+/);
    if (parts.length >= 2) return [parts[0], parts.slice(1).join(" ")]; // keep second as one token
    return [s];
}

function parseCoordinateInput(raw) {
    const parts = normalisePairSeparator(raw);

    if (parts.length !== 2) return { error: "Please provide exactly two values (lat and lon)." };

    const a = parseCoordToken(parts[0]);
    const b = parseCoordToken(parts[1]);
    if (a.error || b.error) return { error: (a.error || b.error) };

    let lat = null, lon = null;

    // If hemispheres tells the role, use them
    if (a.hemi === "N" || a.hemi === "S") lat = a.value * (a.hemi === "S" ? -1 : 1);
    if (a.hemi === "E" || a.hemi === "W") lon = a.value * (a.hemi === "W" ? -1 : 1);
    if (b.hemi === "N" || b.hemi === "S") lat = b.value * (b.hemi === "S" ? -1 : 1);
    if (b.hemi === "E" || b.hemi === "W") lon = b.value * (b.hemi === "W" ? -1 : 1);

    // If still ambiguous, infer by order and ranges
    if (lat === null && lon === null) {
        const aVal = a.value, bVal = b.value;
        const aLooksLat = Math.abs(aVal) <= 90;
        const bLooksLat = Math.abs(bVal) <= 90;
        const aLooksLon = Math.abs(aVal) <= 180;
        const bLooksLon = Math.abs(bVal) <= 180;

        if (aLooksLat && bLooksLon) { lat = aVal; lon = bVal; }
        else if (bLooksLat && aLooksLon) { lat = bVal; lon = aVal; }
        else return { error: "Cannot infer which is latitude vs longitude." };
    } else {
        // Fill the missing one from the remaining token if possible
        if (lat === null) {
            if (Math.abs(a.value) <= 90 && (a.hemi === null || a.hemi === "N" || a.hemi === "S")) lat = a.value * (a.hemi === "S" ? -1 : 1);
            else if (Math.abs(b.value) <= 90) lat = b.value * (b.hemi === "S" ? -1 : 1);
        }
        if (lon === null) {
            if (Math.abs(a.value) <= 180 && (a.hemi === null || a.hemi === "E" || a.hemi === "W")) lon = a.value * (a.hemi === "W" ? -1 : 1);
            else if (Math.abs(b.value) <= 180) lon = b.value * (b.hemi === "W" ? -1 : 1);
        }
    }

    if (!isFinite(lat) || !isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
        return { error: "Latitude/longitude out of range." };
    }
    return { lat, lon };
}

