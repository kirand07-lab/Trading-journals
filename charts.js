(() => {
  const el = document.getElementById("pnlChart");
  if (!el || typeof Chart === "undefined") return;

  const chart = new Chart(el, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Equity",
          data: [],
          borderColor: "rgba(59, 130, 246, 0.95)",
          backgroundColor: "rgba(59, 130, 246, 0.18)",
          fill: true,
          tension: 0.35,
          pointRadius: 2,
          pointHoverRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { mode: "index", intersect: false },
      },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.06)" }, ticks: { color: "rgba(255,255,255,0.65)" } },
        y: { grid: { color: "rgba(255,255,255,0.06)" }, ticks: { color: "rgba(255,255,255,0.65)" } },
      },
    },
  });

  fetch("/analytics/api/charts/pnl_timeseries", { headers: { "Accept": "application/json" } })
    .then((r) => r.ok ? r.json() : Promise.reject(r))
    .then((data) => {
      if (!data || !Array.isArray(data.labels) || !Array.isArray(data.values)) return;
      chart.data.labels = data.labels;
      chart.data.datasets[0].data = data.values;
      chart.update();
    })
    .catch(() => {
      // If the user isn't logged in or has no data, keep the empty chart.
    });
})();

