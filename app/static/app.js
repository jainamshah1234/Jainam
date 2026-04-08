const form = document.getElementById("analyze-form");
const output = document.getElementById("results");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  output.innerHTML = "Analyzing...";

  const formData = new FormData(form);
  const response = await fetch("/demo/analyze-inline", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    output.innerHTML = "Analysis failed. Please try again.";
    return;
  }

  const data = await response.json();
  output.innerHTML = `
    <h3>Plain-English Summary</h3>
    <p>${data.summary}</p>
    <h3>Risky Clauses</h3>
    <ul>${data.risky_clauses.map((c) => `<li>${c}</li>`).join("")}</ul>
    <h3>Suggested Improvements</h3>
    <ul>${data.suggestions.map((s) => `<li>${s}</li>`).join("")}</ul>
    <p><em>Confidence: ${Math.round(data.confidence_score * 100)}%</em></p>
  `;
});
