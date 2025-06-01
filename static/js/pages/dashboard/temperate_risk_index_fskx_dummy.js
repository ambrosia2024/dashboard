document.addEventListener('DOMContentLoaded', function () {
    fetch("/static/data/risk_index.json")
        .then(response => response.json())
        .then(data => {
            const margin = {top: 20, right: 30, bottom: 40, left: 50},
                  width = 600 - margin.left - margin.right,
                  height = 400 - margin.top - margin.bottom;

            const svg = d3.select("#risk_index_chart")
                .html("")  // Clear any previous risk_index_chart
                .append("svg")
                .attr("width", width + margin.left + margin.right)
                .attr("height", height + margin.top + margin.bottom)
                .append("g")
                .attr("transform", `translate(${margin.left},${margin.top})`);

            const x = d3.scaleLinear()
                .domain(d3.extent(data.temp_changes))
                .range([0, width]);

            const y = d3.scaleLinear()
                .domain([0, d3.max(data.risk)])
                .range([height, 0]);

            svg.append("g")
                .attr("transform", `translate(0,${height})`)
                .call(d3.axisBottom(x));

            svg.append("g")
                .call(d3.axisLeft(y));

            svg.append("path")
                .datum(data.temp_changes.map((d, i) => ({x: d, y: data.risk[i]})))
                .attr("fill", "none")
                .attr("stroke", "#007bff")
                .attr("stroke-width", 2)
                .attr("d", d3.line()
                    .x(d => x(d.x))
                    .y(d => y(d.y)));

            svg.selectAll("circle")
                .data(data.temp_changes.map((d, i) => ({x: d, y: data.risk[i]})))
                .enter()
                .append("circle")
                .attr("cx", d => x(d.x))
                .attr("cy", d => y(d.y))
                .attr("r", 3)
                .attr("fill", "#007bff")
                .append("title")
                .text(d => `Temp: ${d.x}°C\nRisk: ${d.y.toFixed(3)}`);

            // On Y axis
            svg.append("text")
                .attr("text-anchor", "middle")
                .attr("transform", `translate(${-35},${height / 2}) rotate(-90)`)
                .style("font-size", "12px")
                .text("Risk Index (0–1)");

            // On X axis
            svg.append("text")
                .attr("text-anchor", "middle")
                .attr("x", width / 2)
                .attr("y", height + 35)
                .style("font-size", "12px")
                .text("Temperature Anomaly (°C)");

            // Chart legend in corner
            svg.append("text")
                .attr("x", width - 10)
                .attr("y", -10)
                .attr("text-anchor", "end")
                .style("font-size", "11px")
                .style("fill", "#007bff")
                .text("Interpolated risk over anomaly");

        });
});
