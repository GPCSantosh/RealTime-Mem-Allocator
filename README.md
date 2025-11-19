#Real-Time Memory Allocation Tracker


## Installation & Setup (Day 3 Update)

### 1. Install dependencies:
pip install flask flask-socketio psutil

### 2. Run the application:
python app.py

### 3. Open in browser:
http://127.0.0.1:5000

This section was added as part of Day 3 revision update.


## Features of the Project (Day 4 Update)

- Real-time memory visualization using frames.
- Dynamic page fault tracking during execution.
- Supports FIFO and LRU page replacement algorithms.
- System RAM usage displayed using psutil.
- Interactive UI with controls for process creation and random access.
- Live updates using Socket.IO communication.
- Helps students understand OS memory management concepts.



## System Architecture Diagram (Day 5 Update)

Below is a simplified visualization of the system architecture used in the
Real-Time Memory Allocation Tracker:

                 +----------------------------+
                 |        Web Browser         |
                 | (HTML, CSS, JS, Canvas UI) |
                 +-------------+--------------+
                               |
                               |  Socket.IO (Real-time Events)
                               v
              +--------------------------------------+
              |              Flask Backend            |
              |   - Memory Manager Module             |
              |   - Pager (FIFO / LRU)                |
              |   - Process Handler                   |
              |   - System RAM Monitor (psutil)       |
              +-------------------+------------------+
                                  |
                                  | Internal Calls
                                  v
              +--------------------------------------+
              |            Data Structures            |
              |   - Frames                           |
              |   - Page Tables                      |
              |   - PID Mapping                      |
              +--------------------------------------+


