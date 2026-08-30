// Small, dependency-free SVG chart helpers. Deliberately not using a CDN
// charting library (Chart.js etc.) so the dashboard keeps working on a LAN
// with no internet access at all, per the EventHub Server spec.
const EventHubCharts = (() => {
    const PALETTE = ["#6c2cff", "#386bff", "#00d4ff", "#a83dff", "#1fb77a", "#f2a83d", "#c9385a", "#637187"];

    function svg(width, height, inner) {
        return `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">${inner}</svg>`;
    }

    function barChart(container, data, { valueKey = "value", labelKey = "label" } = {}) {
        if (!data || !data.length) {
            container.innerHTML = `<p class="hint">Nog geen gegevens.</p>`;
            return;
        }
        const width = 480;
        const rowHeight = 28;
        const height = data.length * rowHeight + 10;
        const maxValue = Math.max(...data.map((d) => d[valueKey]), 1);
        const labelWidth = 130;
        const barMaxWidth = width - labelWidth - 50;
        let inner = "";
        data.forEach((d, index) => {
            const y = index * rowHeight + 6;
            const barWidth = Math.max((d[valueKey] / maxValue) * barMaxWidth, 2);
            const color = PALETTE[index % PALETTE.length];
            const label = String(d[labelKey]).length > 18 ? String(d[labelKey]).slice(0, 17) + "…" : d[labelKey];
            inner += `
                <text x="0" y="${y + 14}" class="chart-bar-label">${label}</text>
                <rect x="${labelWidth}" y="${y}" width="${barWidth}" height="18" rx="4" fill="${color}"></rect>
                <text x="${labelWidth + barWidth + 6}" y="${y + 14}" class="chart-bar-value">${d[valueKey]}</text>
            `;
        });
        container.innerHTML = svg(width, height, inner);
    }

    function donutChart(container, segments) {
        // segments: [{label, value, color}]
        const total = segments.reduce((sum, s) => sum + s.value, 0);
        if (!total) {
            container.innerHTML = `<p class="hint">Nog geen gegevens.</p>`;
            return;
        }
        const size = 200, radius = 80, center = size / 2, strokeWidth = 26;
        const circumference = 2 * Math.PI * radius;
        let offset = 0;
        let circles = "";
        segments.forEach((segment, index) => {
            const fraction = segment.value / total;
            const dash = fraction * circumference;
            const color = segment.color || PALETTE[index % PALETTE.length];
            circles += `<circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="${color}"
                stroke-width="${strokeWidth}" stroke-dasharray="${dash} ${circumference - dash}"
                stroke-dashoffset="${-offset}" transform="rotate(-90 ${center} ${center})"></circle>`;
            offset += dash;
        });
        let legend = "";
        segments.forEach((segment, index) => {
            const color = segment.color || PALETTE[index % PALETTE.length];
            const pct = total ? Math.round((segment.value / total) * 100) : 0;
            legend += `<div style="display:flex;align-items:center;gap:6px;font-size:12px;margin-top:4px;">
                <span style="width:10px;height:10px;border-radius:3px;background:${color};display:inline-block;"></span>
                ${segment.label}: ${segment.value} (${pct}%)
            </div>`;
        });
        container.innerHTML = `
            <div style="display:flex; gap:16px; align-items:center; flex-wrap:wrap;">
                ${svg(size, size, circles).replace("<svg ", `<svg style="max-width:${size}px;" `)}
                <div>${legend}</div>
            </div>`;
    }

    function lineChart(container, points, { xKey = "time", yKey = "cumulative" } = {}) {
        if (!points || !points.length) {
            container.innerHTML = `<p class="hint">Nog geen check-ins.</p>`;
            return;
        }
        const width = 480, height = 180, padding = 30;
        const maxValue = Math.max(...points.map((p) => p[yKey]), 1);
        const stepX = points.length > 1 ? (width - padding * 2) / (points.length - 1) : 0;
        const coords = points.map((p, index) => {
            const x = padding + index * stepX;
            const y = height - padding - (p[yKey] / maxValue) * (height - padding * 2);
            return [x, y];
        });
        const path = coords.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
        const area = `${path} L${coords[coords.length - 1][0].toFixed(1)},${height - padding} L${coords[0][0].toFixed(1)},${height - padding} Z`;
        const labelEvery = Math.max(1, Math.ceil(points.length / 6));
        let labels = "";
        points.forEach((p, index) => {
            if (index % labelEvery !== 0 && index !== points.length - 1) return;
            const [x] = coords[index];
            labels += `<text x="${x}" y="${height - 8}" class="chart-bar-value" text-anchor="middle">${p[xKey]}</text>`;
        });
        const inner = `
            <path d="${area}" fill="#6c2cff22" stroke="none"></path>
            <path d="${path}" fill="none" stroke="#6c2cff" stroke-width="2.5"></path>
            ${labels}
        `;
        container.innerHTML = svg(width, height, inner);
    }

    return { barChart, donutChart, lineChart };
})();
