function fixCoordinate(coord, decimals = 6) {
    if (isFinite(coord) && coord !== null) {
        return parseFloat(coord.toFixed(decimals));
    }
    console.warn(`❌ Invalid coordinate detected: ${coord}`);
    return null;  // Return null for invalid numbers
}

$(document).ready(function () {
    // Ensure Proj4Leaflet is properly loaded
    if (typeof L.Proj === "undefined") {
        console.error("Proj4Leaflet is missing! Ensure you have included proj4.js and proj4leaflet.min.js.");
        return;
    }

    // Define Lambert Conformal Conic Projection (EPSG:3035) for Europe
    var crsLambert = new L.Proj.CRS(
        "EPSG:3035",
        "+proj=lcc +lat_1=35 +lat_2=65 +lon_0=10 +x_0=4321000 +y_0=3210000 +ellps=GRS80 +units=m +no_defs",
        {
            resolutions: [8192, 4096, 2048, 1024, 512, 256, 128, 64, 32, 16, 8, 4, 2, 1],
            origin: [-2000000, 2000000],
            transformation: L.Transformation(1, 0, -1, 0)
        }
    );

    // Initialize map using EPSG:4326 lat/lon coordinates
    var map = L.map('climateMap', {
        crs: crsLambert,
        center: [50.0, 10.0], // Must be in EPSG:4326 format
        zoom: 3
    });

    // Add OpenStreetMap as base layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    // Fetch climate data from Django API
    $.getJSON("/api/climate-data/", function (geojsonData) {
        console.log("✅ Climate Data Loaded:", geojsonData);

        // Function to determine marker color based on temperature
        function getColor(temp) {
            return temp > 30 ? "#FF0000" :
                   temp > 20 ? "#FF7F00" :
                   temp > 10 ? "#FFFF00" :
                   temp > 0  ? "#00FF00" :
                   temp > -10 ? "#0080FF" :
                                "#0000FF";
        }

        // Function to validate and fix floating-point precision in coordinates
        function fixCoordinate(coord, decimals = 6) {
            if (isFinite(coord) && coord !== null) {
                return parseFloat(coord.toFixed(decimals));
            }
            return null; // Return null for invalid values
        }

        // Function to validate latitude and longitude
        function isValidLatLon(lat, lon) {
            return isFinite(lat) && isFinite(lon) &&
                   lat !== null && lon !== null &&
                   lat >= 35 && lat <= 71 &&  // Europe Latitude Range
                   lon >= -25 && lon <= 45;   // Europe Longitude Range
        }

        // Debugging: Log invalid points before filtering
        geojsonData.features.forEach(feature => {
            let lon = fixCoordinate(feature.geometry.coordinates[0]);
            let lat = fixCoordinate(feature.geometry.coordinates[1]);

            if (!isValidLatLon(lat, lon)) {
                console.warn(`❌ Skipping invalid coordinates: lat=${lat}, lon=${lon}`);
            } else {
                console.log(`✅ Valid point: lat=${lat}, lon=${lon}`);
            }
        });

        // Add temperature data as circle markers (only for valid points)
        L.geoJSON(geojsonData, {
            filter: function (feature) {
                if (!feature.geometry || !feature.geometry.coordinates) {
                    console.warn("❌ Skipping feature with missing geometry:", feature);
                    return false;
                }

                let lon = fixCoordinate(feature.geometry.coordinates[0]);
                let lat = fixCoordinate(feature.geometry.coordinates[1]);

                if (!lon || !lat) {
                    console.warn(`❌ Skipping invalid coordinates: lat=${lat}, lon=${lon}`);
                    return false;
                }
                return true;
            },
            pointToLayer: function (feature, latlng) {
                return L.circleMarker(latlng, {
                    radius: 5,
                    fillColor: getColor(feature.properties.temperature),
                    color: "#000",
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                }).bindPopup(
                    `<b>Temperature:</b> ${feature.properties.temperature}°C<br>
                     <b>Timestamp:</b> ${feature.properties.timestamp}`
                );
            }
        }).addTo(map);
    }).fail(function () {
        console.error("❌ Error loading climate data.");
    });
});
