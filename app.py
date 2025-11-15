# app.py - Realtime Memory Allocation Tracker (Backend)

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from collections import deque, OrderedDict
import psutil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret'

# Simple safe async mode (no eventlet needed)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# -------------------- Core Classes --------------------

class Frame:
    def __init__(self, idx):
        self.idx = idx
        self.pid = None
        self.label = None

    def is_free(self):
        return self.pid is None


class MemoryManager:
    def __init__(self, total_kb=1024, frame_kb=64):
        self.total_kb = total_kb
        self.frame_kb = frame_kb
        self.frames = []
        self.free_frames = set()
        self.pid_to_frames = {}
        self.page_faults = 0
        self.allocations = 0
        self.deallocations = 0
        self._rebuild()

    def _rebuild(self):
        n = max(1, self.total_kb // self.frame_kb)
        self.frames = [Frame(i) for i in range(n)]
        self.free_frames = set(range(n))
        self.pid_to_frames.clear()
        self.page_faults = 0
        self.allocations = 0
        self.deallocations = 0

    def reset(self, total_kb=None, frame_kb=None):
        if total_kb is not None:
            self.total_kb = total_kb
        if frame_kb is not None:
            self.frame_kb = frame_kb
        self._rebuild()

    def used_and_total(self):
        used = sum(1 for f in self.frames if not f.is_free())
        return used, len(self.frames)

    def alloc_pages(self, pid, num_pages):
        if num_pages > len(self.free_frames):
            return False, "Not enough free frames"
        chosen = []
        for _ in range(num_pages):
            fidx = self.free_frames.pop()
            f = self.frames[fidx]
            f.pid = pid
            f.label = None
            chosen.append(fidx)
        self.pid_to_frames.setdefault(pid, set()).update(chosen)
        self.allocations += 1
        return True, f"Allocated {num_pages} frames to {pid}"

    def free_pid(self, pid):
        if pid not in self.pid_to_frames:
            return False, "PID not found"
        for fidx in list(self.pid_to_frames[pid]):
            f = self.frames[fidx]
            f.pid = None
            f.label = None
            self.free_frames.add(fidx)
        del self.pid_to_frames[pid]
        self.deallocations += 1
        return True, f"Deallocated {pid}"


class Pager:
    def __init__(self, mem: MemoryManager, algorithm="FIFO"):
        self.mem = mem
        self.algorithm = algorithm       # "FIFO" or "LRU"
        self.page_tables = {}            # pid -> {page_no: frame_idx or None}
        self.fifo = deque()              # FIFO queue of frame indices
        self.lru = OrderedDict()         # LRU: key=(pid,page), value=timestamp

    def reset(self, algorithm=None):
        if algorithm is not None:
            self.algorithm = algorithm
        self.page_tables.clear()
        self.fifo.clear()
        self.lru.clear()

    def create_process(self, pid, num_pages):
        self.page_tables[pid] = {p: None for p in range(num_pages)}

    def deallocate_pid(self, pid):
        if pid not in self.page_tables:
            return
        for p, fidx in list(self.page_tables[pid].items()):
            if fidx is not None:
                f = self.mem.frames[fidx]
                f.pid = None
                f.label = None
                self.mem.free_frames.add(fidx)
        del self.page_tables[pid]
        keys = [k for k in self.lru if k[0] == pid]
        for k in keys:
            self.lru.pop(k, None)

    def access_page(self, pid, page_no):
        self.mem.page_faults += 1
        pt = self.page_tables.setdefault(pid, {})
        # Hit
        if page_no in pt and pt[page_no] is not None:
            if self.algorithm == "LRU":
                key = (pid, page_no)
                self.lru[key] = time.time()
                self.lru.move_to_end(key)
            return True, "hit"

        # Need a frame
        if self.mem.free_frames:
            fidx = self.mem.free_frames.pop()
        else:
            # choose victim
            if self.algorithm == "FIFO":
                fidx = self.fifo.popleft() if self.fifo else random.randrange(len(self.mem.frames))
            else:  # LRU
                if self.lru:
                    (vpid, vp), _ = self.lru.popitem(last=False)
                    old_frame = self.page_tables[vpid][vp]
                    if old_frame is not None:
                        f = self.mem.frames[old_frame]
                        f.pid = None
                        f.label = None
                        self.mem.free_frames.add(old_frame)
                    self.page_tables[vpid][vp] = None
                    fidx = old_frame if old_frame is not None else random.randrange(len(self.mem.frames))
                else:
                    fidx = random.randrange(len(self.mem.frames))

        f = self.mem.frames[fidx]
        f.pid = pid
        f.label = f"p{page_no}"
        self.mem.pid_to_frames.setdefault(pid, set()).add(fidx)
        pt[page_no] = fidx

        if self.algorithm == "FIFO":
            self.fifo.append(fidx)
        else:
            key = (pid, page_no)
            self.lru[key] = time.time()
            self.lru.move_to_end(key)

        return True, f"loaded in frame {fidx}"

# -------------------- Global Simulation State --------------------

SIM = {
    "mem": MemoryManager(1024, 64),
    "pager": None,
    "mode": "Paging",      # or "Segmentation" if you want later
    "algorithm": "FIFO",
    "next_pid": 1,
    "running": False,
    "run_interval": 0.6,
}

SIM["pager"] = Pager(SIM["mem"], SIM["algorithm"])

# -------------------- Helper Functions --------------------

def system_memory_snapshot():
    try:
        vm = psutil.virtual_memory()
        return {
            "total_kb": vm.total // 1024,
            "used_kb": (vm.total - vm.available) // 1024,
            "available_kb": vm.available // 1024,
            "percent": vm.percent,
        }
    except Exception:
        return None

def state_snapshot():
    mem = SIM["mem"]
    frames = [{"idx": f.idx, "pid": f.pid, "label": f.label} for f in mem.frames]
    used, total = mem.used_and_total()
    pids = set(mem.pid_to_frames.keys())
    pids.update(SIM["pager"].page_tables.keys())

    return {
        "frames": frames,
        "used": used,
        "total": total,
        "page_faults": mem.page_faults,
        "allocations": mem.allocations,
        "deallocations": mem.deallocations,
        "pids": sorted(pids),
        "system_mem": system_memory_snapshot(),
    }

def broadcast_state():
    socketio.emit("state_update", state_snapshot())

def sim_step():
    # simple random paging behaviour
    if not SIM["pager"].page_tables:
        pid = f"P{SIM['next_pid']}"
        SIM["next_pid"] += 1
        pages = random.randint(2, 8)
        SIM["pager"].create_process(pid, pages)
        for p in range(pages):
            SIM["pager"].access_page(pid, p)
        return

    pid = random.choice(list(SIM["pager"].page_tables.keys()))
    pages = list(SIM["pager"].page_tables[pid].keys())
    if not pages:
        return
    p = random.choice(pages)
    SIM["pager"].access_page(pid, p)

def run_loop():
    while True:
        socketio.sleep(0.1)
        if SIM["running"]:
            sim_step()
            broadcast_state()

def broadcaster_loop():
    while True:
        socketio.sleep(1.0)
        broadcast_state()

# -------------------- Flask Routes --------------------

@app.route("/")
def index():
    return render_template("index.html")

# -------------------- Socket.IO Events --------------------

@socketio.on("connect")
def on_connect():
    emit("state_update", state_snapshot())

@socketio.on("apply_config")
def on_apply_config(data):
    total = int(data.get("total_kb", 1024))
    frame = int(data.get("frame_kb", 64))
    mode = data.get("mode", "Paging")
    algo = data.get("algorithm", "FIFO")

    SIM["mode"] = mode
    SIM["algorithm"] = algo

    SIM["mem"].reset(total_kb=total, frame_kb=frame)
    SIM["pager"] = Pager(SIM["mem"], algo)
    SIM["next_pid"] = 1
    broadcast_state()

@socketio.on("create_process")
def on_create_process(data):
    size = int(data.get("size", 200))
    frame_kb = SIM["mem"].frame_kb
    pages = max(1, (size + frame_kb - 1) // frame_kb)
    pid = f"P{SIM['next_pid']}"
    SIM["next_pid"] += 1
    SIM["pager"].create_process(pid, pages)
    SIM["pager"].access_page(pid, 0)
    emit("action_result", {"ok": True, "msg": f"Created {pid} with {pages} pages"})
    SIM["pager"].create_process(pid, pages)
    SIM["pager"].access_page(pid, 0)
    SIM["mem"].allocations += 1
    broadcast_state()

@socketio.on("deallocate")
def on_deallocate(data):
    pid = data.get("pid")
    if not pid:
        emit("action_result", {"ok": False, "msg": "No PID"})
        return
    SIM["pager"].deallocate_pid(pid)
    SIM["mem"].free_pid(pid)
    emit("action_result", {"ok": True, "msg": f"Deallocated {pid}"})
    broadcast_state()

@socketio.on("step")
def on_step(_data):
    sim_step()
    broadcast_state()

@socketio.on("toggle_run")
def on_toggle_run(data):
    SIM["running"] = bool(data.get("start", True))
    SIM["run_interval"] = float(data.get("interval", SIM["run_interval"]))
    emit("action_result", {"ok": True, "msg": f"Running={SIM['running']}"})

@socketio.on("random_access")
def on_random_access(_data):
    for _ in range(5):
        sim_step()
    broadcast_state()

# -------------------- Main Entry --------------------

if __name__ == "__main__":
    print("[app.py] starting on http://127.0.0.1:5000")
    socketio.start_background_task(run_loop)
    socketio.start_background_task(broadcaster_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
