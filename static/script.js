document.getElementById("recommendForm").addEventListener("submit", function (e) {
    e.preventDefault();

    // Get values safely
    const category = document.getElementById("category").value;
    const fragility = document.getElementById("fragility").value;
    const shipping = document.getElementById("shipping").value;
    const sustainability = document.getElementById("sustainability").value;

    const data = {
        category,
        fragility,
        shipping,
        sustainability
    };

    fetch("/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    })
        .then(res => res.json())
        .then(result => {

            const resultsDiv = document.getElementById("results");
            resultsDiv.innerHTML = "";

            // Safety check
            if (!Array.isArray(result) || result.length === 0) {
                resultsDiv.innerHTML = `
                    <div class="alert alert-danger">
                        No recommendations found
                    </div>
                `;
                return;
            }

            let materials = [];
            let scores = [];
            let co2Trend = [];
            let costTrend = [];

            let totalCO2 = 0;
            let totalCost = 0;

            result.forEach((item, index) => {

                materials.push(item.material);
                scores.push(Number(item.final_score));
                co2Trend.push(Number(item.co2_reduction_percent));
                costTrend.push(Number(item.cost_saving));

                totalCO2 += Number(item.co2_reduction_percent);
                totalCost += Number(item.cost_saving);

                let co2Class = item.co2_reduction_percent >= 0 ? "text-success" : "text-danger";

                resultsDiv.innerHTML += `
                    <div class="card mb-3 p-3 shadow-sm material-card">
                        <h5 class="fw-bold text-success">
                            ${index + 1}. ${item.material}
                        </h5>
                        <p><strong>Predicted Cost:</strong> ${item.predicted_cost}</p>
                        <p><strong>Predicted CO₂:</strong> ${item.predicted_co2}</p>
                        <p class="${co2Class}">
                            <strong>CO₂ Impact:</strong> ${item.co2_reduction_percent}%
                        </p>
                        <p><strong>Cost Saving:</strong> ${item.cost_saving}</p>
                        <p><strong>Final Score:</strong> ${item.final_score}</p>
                    </div>
                `;
            });

            let avgCO2 = (totalCO2 / result.length).toFixed(2);
            let avgCost = (totalCost / result.length).toFixed(2);

            // Add summary cards on top
            resultsDiv.innerHTML =
                `
                <div class="row mb-4">
                    <div class="col-md-6">
                        <div class="card bg-success text-white text-center p-3">
                            <h6>Average CO₂ Reduction</h6>
                            <h4>${avgCO2}%</h4>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card bg-primary text-white text-center p-3">
                            <h6>Average Cost Saving</h6>
                            <h4>${avgCost}</h4>
                        </div>
                    </div>
                </div>
                ` + resultsDiv.innerHTML;

            // ------------------ CHARTS ------------------

            // Vertical Bar Chart
            Plotly.newPlot("verticalBar", [{
                x: materials,
                y: scores,
                type: "bar",
                marker: { color: "#198754" }
            }], {
                title: "Material Comparison (Final Score)",
                margin: { t: 50 }
            });

            // Horizontal Ranking Chart
            Plotly.newPlot("horizontalBar", [{
                x: scores,
                y: materials,
                type: "bar",
                orientation: "h",
                marker: { color: "#0d6efd" }
            }], {
                title: "Ranking Overview",
                margin: { l: 150 }
            });

            // Line Chart (Dual Line)
            Plotly.newPlot("lineChart", [
                {
                    x: materials,
                    y: co2Trend,
                    type: "scatter",
                    mode: "lines+markers",
                    name: "CO₂ Reduction %",
                    line: { color: "#198754" }
                },
                {
                    x: materials,
                    y: costTrend,
                    type: "scatter",
                    mode: "lines+markers",
                    name: "Cost Saving",
                    line: { color: "#0d6efd" }
                }
            ], {
                title: "CO₂ & Cost Trend Analysis",
                margin: { t: 50 }
            });

            // Pie Chart (Usage Distribution)
            fetch("/usage")
                .then(res => res.json())
                .then(data => {

                    if (Object.keys(data).length > 0) {
                        Plotly.newPlot("pieChart", [{
                            labels: Object.keys(data),
                            values: Object.values(data),
                            type: "pie"
                        }], {
                            title: "Material Usage Distribution"
                        });
                    }
                });

            document.getElementById("resultsCard").classList.remove("d-none");
        })
        .catch(error => {
            console.error("Error:", error);
        });
});