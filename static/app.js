// app.js - Realtime Memory Tracker Frontend

const socket = io();

let state = null;
const canvas = document.getElementById("memCanvas");
const ctx = canvas.getContext("2d");

function resizeCanvas() {
  canvas.width = canvas.clientWidth * devicePixelRatio;
  canvas.height = canvas.clientHeight * devicePixelRatio;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  render();
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

socket.on("state_update", (s) => {
  state = s;
  updateInfo();
  render();
});

socket.on("action_result", (d) => {
  if (!d.ok) alert(d.msg || "Action failed");
});

// Update side panel
function updateInfo() {
  if (!state) return;
  document.getElementById("status").textContent =
    `Frames used: ${state.used}/${state.total}`;
  document.getElementById("pf").textContent =
    `Page Faults: ${state.page_faults}`;
  document.getElementById("allocs").textContent =
    `Allocations: ${state.allocations}`;
  document.getElementById("deallocs").textContent =
    `Deallocations: ${state.deallocations}`;
  document.getElementById("plist").textContent =
    `Processes: ${state.pids.length ? state.pids.join(", ") : "None"}`;

  if (state.system_mem) {
    const sm = state.system_mem;
    document.getElementById("sys_total").textContent =
      `Total: ${Math.round(sm.total_kb / 1024)} MB`;
    document.getElementById("sys_used").textContent =
      `Used: ${Math.round(sm.used_kb / 1024)} MB`;
    document.getElementById("sys_pct").textContent =
      `Usage: ${sm.percent}%`;
  }
}

// Draw memory frames
function render() {
  if (!state) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }

  const padding = 16;
  const w = canvas.clientWidth - padding * 2;
  const h = canvas.clientHeight - padding * 2;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const frames = state.frames || [];
  if (!frames.length) return;

  const cols = Math.ceil(Math.sqrt(frames.length));
  const rows = Math.ceil(frames.length / cols);

  const cellW = w / cols;
  const cellH = h / rows;

  frames.forEach((f, idx) => {
    const r = Math.floor(idx / cols);
    const c = idx % cols;
    const x = padding + c * cellW;
    const y = padding + r * cellH;

    ctx.fillStyle = f.pid ? colorFromString(String(f.pid)) : "#1f2933";
    ctx.fillRect(x, y, cellW - 4, cellH - 4);

    ctx.fillStyle = "#fff";
    ctx.font = "11px sans-serif";
    ctx.fillText(f.pid ? f.pid : "Free", x + 6, y + 16);
    if (f.label) {
      ctx.fillText(f.label, x + 6, y + 30);
    }
  });
}

function colorFromString(s) {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = s.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 65%, 50%)`;
}

// Controls
document.getElementById("apply-btn").onclick = () => {
  socket.emit("apply_config", {
    total_kb: parseInt(document.getElementById("total_kb").value),
    frame_kb: parseInt(document.getElementById("frame_kb").value),
    mode: document.getElementById("mode-select").value,
    algorithm: document.getElementById("algo-select").value,
  });
};

document.getElementById("create-btn").onclick = () => {
  const size = parseInt(document.getElementById("proc-size").value);
  socket.emit("create_process", { size });
};

document.getElementById("dealloc-btn").onclick = () => {
  const pid = prompt("Enter PID to deallocate:");
  if (pid) socket.emit("deallocate", { pid });
};

document.getElementById("step-btn").onclick = () => {
  socket.emit("step", {});
};

document.getElementById("random-btn").onclick = () => {
  socket.emit("random_access", {});
};

// Keep re-rendering in case of resize
setInterval(() => render(), 300);
