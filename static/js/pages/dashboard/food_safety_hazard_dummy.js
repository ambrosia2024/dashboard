const data = [
    { time: 0, hazard1: 0, hazard2: 0 },
    { time: 1, hazard1: 1.2, hazard2: 1.4 },
    { time: 2, hazard1: 2.3, hazard2: 2.8 },
    { time: 3, hazard1: 3.6, hazard2: 4.5 },
    { time: 4, hazard1: 5.1, hazard2: 6.0 },
    { time: 5, hazard1: 6.7, hazard2: 7.5 },
    { time: 6, hazard1: 8.2, hazard2: 9.1 },
    { time: 7, hazard1: 9.5, hazard2: 10.3 },
    { time: 8, hazard1: 11.0, hazard2: 11.9 },
    { time: 9, hazard1: 12.4, hazard2: 13.2 }
];


const width = 700, height = 500;
const margin = { top: 50, right: 50, bottom: 50, left: 60 };

const svg = d3.select("#chart")
    .append("svg")
    .attr("width", width)
    .attr("height", height)
    .append("g")
    .attr("transform", `translate(${margin.left}, ${margin.top})`);

const xScale = d3.scaleLinear()
    .domain(d3.extent(data, d => d.time))
    .range([0, width - margin.left - margin.right]);

const yScale = d3.scaleLinear()
    .domain([0, d3.max(data, d => Math.max(d.hazard1, d.hazard2))])
    .range([height - margin.top - margin.bottom, 0]);

// Add Gridlines
const grid = svg.append("g")
    .attr("class", "grid")
    .call(d3.axisLeft(yScale).tickSize(-width + margin.left + margin.right).tickFormat(""));

grid.selectAll("line")
    .attr("stroke", "#ddd")
    .attr("stroke-dasharray", "4,4");

const line1 = d3.line()
    .x(d => xScale(d.time))
    .y(d => yScale(d.hazard1))
    .curve(d3.curveMonotoneX);

const line2 = d3.line()
    .x(d => xScale(d.time))
    .y(d => yScale(d.hazard2))
    .curve(d3.curveMonotoneX);

svg.append("path")
    .datum(data)
    .attr("fill", "none")
    .attr("stroke", "steelblue")
    .attr("stroke-width", 3)
    .attr("d", line1);

svg.append("path")
    .datum(data)
    .attr("fill", "none")
    .attr("stroke", "green")
    .attr("stroke-width", 3)
    .attr("d", line2);

// Add Axis Labels
svg.append("g")
    .attr("transform", `translate(0,${height - margin.bottom - margin.top})`)
    .call(d3.axisBottom(xScale))
    .append("text")
    .attr("x", (width - margin.left - margin.right) / 2)
    .attr("y", 40)
    .attr("text-anchor", "middle")
    .attr("fill", "black")
    .style("font-size", "14px")
    .text("Time (Weeks/Years)");

svg.append("g")
    .call(d3.axisLeft(yScale));

svg.append("text")
    .attr("transform", "rotate(-90)")
    .attr("x", -(height - margin.top - margin.bottom) / 2)
    .attr("y", -margin.left + 15)
    .attr("text-anchor", "middle")
    .attr("fill", "black")
    .style("font-size", "14px")
    .text("Risk of Hazard");

// Add Title
svg.append("text")
    .attr("x", (width - margin.left - margin.right) / 2)
    .attr("y", -20)
    .attr("text-anchor", "middle")
    .style("font-size", "18px")
    .style("font-weight", "bold")
    .text("Food Safety Hazard for Wheat in Amersfoort");

// Add Legend
const legend = svg.append("g")
    .attr("transform", `translate(${width - margin.right - 150}, 10)`);

legend.append("rect")
    .attr("x", 0)
    .attr("y", 0)
    .attr("width", 15)
    .attr("height", 15)
    .attr("fill", "steelblue");

legend.append("text")
    .attr("x", 20)
    .attr("y", 12)
    .style("font-size", "12px")
    .text("Hazard Type 1");

legend.append("rect")
    .attr("x", 0)
    .attr("y", 20)
    .attr("width", 15)
    .attr("height", 15)
    .attr("fill", "green");

legend.append("text")
    .attr("x", 20)
    .attr("y", 32)
    .style("font-size", "12px")
    .text("Hazard Type 2");