$(function () {
    // Initial render
    renderPastHazards("all");
    renderFutureHazards();

    // Year filter change
    $("#yearFilter").on("change", function () {
        const selectedYear = $(this).val();
        $("#past-hazards-list").empty();  // clear old list
        renderPastHazards(selectedYear);
    });
});

function renderPastHazards(filterYear) {
    const data = [
        { date: "2021-03-15", hazard: "E. coli in spinach", category: "Biological" },
        { date: "2022-06-07", hazard: "Listeria in cheese", category: "Biological" },
        { date: "2023-01-12", hazard: "Salmonella in chicken", category: "Biological" },
        { date: "2022-11-05", hazard: "Aflatoxin in peanuts", category: "Chemical" }
    ];

    const icons = {
        Biological: "🦠",
        Chemical: "☣️",
        Physical: "⚙️"
    };

    const container = d3.select("#past-hazards-list");

    const filtered = (filterYear === "all")
        ? data
        : data.filter(d => d.date.startsWith(filterYear));

    container.selectAll("li")
        .data(filtered)
        .enter()
        .append("li")
        .html(d => `${icons[d.category] || ""} <strong>${d.date}</strong> — ${d.hazard} <em>(${d.category})</em>`);
}

function renderFutureHazards() {
    const data = [
        { name: "Aflatoxin B1 (mycotoxin)", category: "Chemical" },
        { name: "Vibrio spp. (linked to warming oceans)", category: "Biological" },
        { name: "Fusarium toxins in maize", category: "Chemical" }
    ];

    const icons = {
        Biological: "🦠",
        Chemical: "☣️",
        Physical: "⚙️"
    };

    const container = d3.select("#future-hazards-list");

    container.selectAll("li")
        .data(data)
        .enter()
        .append("li")
        .html(d => `${icons[d.category] || ""} ${d.name} <em>(${d.category})</em>`);
}
