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
        var query = $("#searchAddress").val().trim();

        if (!query) {
            alert("Please enter a location.");
            return;
        }

        $("#searchButton").prop("disabled", true).text("Searching...");
        $("#loadingMessage").show();

        var url = `https://nominatim.openstreetmap.org/search?format=json&q=${query}&addressdetails=1`;

        $.getJSON(url, function (data) {
            if (data.length === 0) {
                alert("Location not found. Try another search.");
                resetSearchButton();
                return;
            }

            // Clear previous results
            $("#locationResults").empty().show();

            // Display all matching locations in a list
            data.forEach((location, index) => {
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

                console.log("Selected NUTS2 Region:", selectedRegion.properties.NUTS_ID);
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
});