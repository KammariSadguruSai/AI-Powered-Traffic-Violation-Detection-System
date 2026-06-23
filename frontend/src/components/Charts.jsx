import {
  Chart as ChartJS,
  ArcElement, Tooltip, Legend,
  CategoryScale, LinearScale, BarElement, PointElement, LineElement,
  Filler, Title,
} from "chart.js";
import { Doughnut, Bar, Line } from "react-chartjs-2";

ChartJS.register(
  ArcElement, Tooltip, Legend,
  CategoryScale, LinearScale, BarElement, PointElement, LineElement,
  Filler, Title
);

const VIOLATION_COLORS = [
  "#ef4444", "#f59e0b", "#f97316", "#a855f7",
  "#3b82f6", "#dc2626", "#8b5cf6", "#06b6d4",
];

export function ViolationPieChart({ data = [] }) {
  const chartData = {
    labels: data.map((d) =>
      d.violation_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    ),
    datasets: [
      {
        data: data.map((d) => d.count),
        backgroundColor: VIOLATION_COLORS.slice(0, data.length).map((c) => c + "cc"),
        borderColor: VIOLATION_COLORS.slice(0, data.length),
        borderWidth: 2,
        hoverOffset: 8,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "right",
        labels: {
          color: "#94a3b8",
          font: { size: 12, family: "Inter" },
          padding: 16,
          usePointStyle: true,
        },
      },
      tooltip: {
        backgroundColor: "#15152a",
        borderColor: "rgba(99,102,241,0.2)",
        borderWidth: 1,
        titleColor: "#f1f5f9",
        bodyColor: "#94a3b8",
        padding: 12,
        callbacks: {
          label: (ctx) => ` ${ctx.label}: ${ctx.raw} (${data[ctx.dataIndex]?.percentage}%)`,
        },
      },
    },
    cutout: "65%",
  };

  return (
    <div style={{ height: 260, position: "relative" }}>
      {data.length === 0 ? (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          height: "100%", color: "var(--text-muted)", fontSize: 14,
        }}>
          No data yet
        </div>
      ) : (
        <Doughnut data={chartData} options={options} />
      )}
    </div>
  );
}

export function ViolationBarChart({ data = [] }) {

  const chartData = {
    labels: data.map((d) =>
      d.violation_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    ),
    datasets: [
      {
        label: "Violations",
        data: data.map((d) => d.count),
        backgroundColor: "rgba(99,102,241,0.7)",
        borderColor: "#6366f1",
        borderWidth: 2,
        borderRadius: 6,
        borderSkipped: false,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#15152a",
        borderColor: "rgba(99,102,241,0.2)",
        borderWidth: 1,
        titleColor: "#f1f5f9",
        bodyColor: "#94a3b8",
        padding: 12,
      },
    },
    scales: {
      x: {
        grid: { color: "rgba(99,102,241,0.06)" },
        ticks: { color: "#94a3b8", font: { size: 11 } },
      },
      y: {
        grid: { color: "rgba(99,102,241,0.06)" },
        ticks: { color: "#94a3b8", font: { size: 11 } },
      },
    },
  };

  return (
    <div style={{ height: 260 }}>
      <Bar data={chartData} options={options} />
    </div>
  );
}

export function TrendLineChart({ data = [], period = "daily" }) {

  const chartData = {
    labels: data.map((d) => d.date),
    datasets: [
      {
        label: "Violations",
        data: data.map((d) => d.count),
        borderColor: "#6366f1",
        backgroundColor: "rgba(99,102,241,0.1)",
        borderWidth: 2.5,
        fill: true,
        tension: 0.4,
        pointBackgroundColor: "#6366f1",
        pointBorderColor: "#0a0a12",
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#15152a",
        borderColor: "rgba(99,102,241,0.2)",
        borderWidth: 1,
        titleColor: "#f1f5f9",
        bodyColor: "#94a3b8",
        padding: 12,
      },
    },
    scales: {
      x: {
        grid: { color: "rgba(99,102,241,0.06)" },
        ticks: { color: "#94a3b8", font: { size: 11 }, maxTicksLimit: 10 },
      },
      y: {
        grid: { color: "rgba(99,102,241,0.06)" },
        ticks: { color: "#94a3b8", font: { size: 11 } },
        beginAtZero: true,
      },
    },
  };

  return (
    <div style={{ height: 260 }}>
      <Line data={chartData} options={options} />
    </div>
  );
}
