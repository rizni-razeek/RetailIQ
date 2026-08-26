(function () {
  "use strict";

  const registry = new Map();

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function palette() {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
      primary: token(dark ? "--color-primary-400" : "--color-primary-700"),
      primaryMid: token("--color-primary-500"),
      primaryLight: token("--color-primary-300"),
      primaryDeep: token(dark ? "--color-primary-300" : "--color-primary-900"),
      success: token("--color-success-icon"),
      warning: token("--color-warning-icon"),
      danger: token("--color-danger-icon"),
      info: token("--color-info-icon"),
      text: token("--text-body"),
      secondary: token("--text-secondary"),
      grid: token("--border-default"),
      tooltip: token("--surface-brand"),
      tooltipText: token("--text-on-brand"),
    };
  }

  function colour(name, colours) {
    return colours[name] || colours.primary;
  }

  function chartOptions(spec, colours) {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    return {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: spec.indexAxis || "x",
      animation: reducedMotion ? false : { duration: 240 },
      interaction: { intersect: false, mode: spec.interactionMode || "index" },
      plugins: {
        legend: {
          display: Boolean(spec.showLegend),
          position: "bottom",
          labels: {
            color: colours.text,
            boxWidth: 12,
            boxHeight: 12,
            font: { family: "Figtree", size: 12 },
          },
        },
        tooltip: {
          backgroundColor: colours.tooltip,
          titleColor: colours.tooltipText,
          bodyColor: colours.tooltipText,
          padding: 12,
          cornerRadius: 8,
          titleFont: { family: "Figtree", weight: "600" },
          bodyFont: { family: "JetBrains Mono" },
        },
      },
      scales: {
        x: {
          beginAtZero: spec.indexAxis === "y",
          grid: { display: spec.indexAxis === "y", color: colours.grid },
          border: { color: colours.grid },
          ticks: {
            color: colours.secondary,
            autoSkip: true,
            maxTicksLimit: spec.maxTicks || 8,
            font: { family: "JetBrains Mono", size: 11 },
          },
          title: spec.xTitle ? {
            display: true,
            text: spec.xTitle,
            color: colours.secondary,
            font: { family: "Figtree", size: 12, weight: "600" },
          } : { display: false },
        },
        y: {
          beginAtZero: true,
          grid: { display: spec.indexAxis !== "y", color: colours.grid },
          border: { color: colours.grid },
          ticks: {
            color: colours.secondary,
            font: { family: spec.indexAxis === "y" ? "Figtree" : "JetBrains Mono", size: 11 },
          },
          title: spec.yTitle ? {
            display: true,
            text: spec.yTitle,
            color: colours.secondary,
            font: { family: "Figtree", size: 12, weight: "600" },
          } : { display: false },
        },
      },
    };
  }

  function render(canvas, spec) {
    if (!window.Chart || !canvas) return false;
    const current = registry.get(canvas);
    if (current) current.chart.destroy();
    const colours = palette();
    const datasets = spec.datasets.map(function (dataset) {
      const selected = colour(dataset.tone, colours);
      return Object.assign({
        borderColor: selected,
        backgroundColor: selected,
        borderWidth: dataset.type === "line" || spec.type === "line" ? 2 : 0,
        pointRadius: dataset.type === "line" || spec.type === "line" ? 0 : undefined,
        pointHoverRadius: dataset.type === "line" || spec.type === "line" ? 4 : undefined,
        tension: dataset.type === "line" || spec.type === "line" ? 0.18 : undefined,
      }, dataset, { tone: undefined });
    });
    const chart = new window.Chart(canvas, {
      type: spec.type,
      data: { labels: spec.labels, datasets: datasets },
      options: chartOptions(spec, colours),
    });
    registry.set(canvas, { chart: chart, spec: spec });
    return true;
  }

  function destroy(canvas) {
    const current = registry.get(canvas);
    if (current) {
      current.chart.destroy();
      registry.delete(canvas);
    }
  }

  document.addEventListener("retailiq:theme-changed", function () {
    Array.from(registry.entries()).forEach(function (entry) {
      render(entry[0], entry[1].spec);
    });
  });

  window.RetailIQCharts = {
    create: render,
    destroy: destroy,
    isAvailable: function () { return Boolean(window.Chart); },
  };
})();
