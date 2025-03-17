# Internet Protocols Project 1

This project implements and compares the performance of HTTP/1.1, HTTP/2, and BitTorrent protocols by transferring files of different sizes between servers and measuring throughput, transfer time, and protocol overhead.

## Setup Instructions

### Install Python packages
We recommend using a virtual environment before starting the project setup.
```bash
pip install -r requirements.txt 
```

### Configure Machine IPs

Modify `machines.json` to set the IP addresses of your virtual machines:

```json
{
    "vm1": "192.168.254.129",
    "vm2": "192.168.254.130",
    "vm3": "192.168.254.131",
    "vm4": "192.168.254.132"
}
```

Replace the IP addresses with the actual IPs of your machines.

## Running Experiments

Run the experiments in sequence as follows:

### HTTP/1.1 Experiments

1. **First Run: VM1 → VM2**
   - Start the server on VM1:
     ```bash
     python http1.1/server.py
     ```
   - Run the client on VM2 to download A files:
     ```bash
     python http1.1/client.py --server vm1 --file A
     ```
   - This will create a results file: `http1.1/results_A_from_vm1_http1.json` on VM2

2. **Second Run: VM2 → VM1**
   - Start the server on VM2:
     ```bash
     python http1.1/server.py
     ```
   - Run the client on VM1 to download B files:
     ```bash
     python http1.1/client.py --server vm2 --file B
     ```
   - This will create a results file: `http1.1/results_B_from_vm2_http1.json` on VM1

### HTTP/2 Experiments

1. **First Run: VM1 → VM2**
   - Start the server on VM1:
     ```bash
     python http2/server.py
     ```
   - Run the client on VM2 to download A files:
     ```bash
     python http2/client.py --server vm1 --file A
     ```
   - This will create a results file: `http2/results_A_from_vm1_http2.json` on VM2

2. **Second Run: VM2 → VM1**
   - Start the server on VM2:
     ```bash
     python http2/server.py
     ```
   - Run the client on VM1 to download B files:
     ```bash
     python http2/client.py --server vm2 --file B
     ```
   - This will create a results file: `http2/results_B_from_vm2_http2.json` on VM1

### BitTorrent Experiments

BitTorrent experiments require four computers (or VMs). One computer will have the initial file, and all four computers will participate in the file exchange using the BitTorrent protocol. We are using opentracker udp protocol as our tracker.

#### Running BitTorrent Experiments

For each file size, follow these steps:

1. **Start the Seeder on VM1**:
   ```bash
   # General format:
   python bitTorrent/seeder.py /path/to/file
   
   # Example for A_10kB:
   python bitTorrent/seeder.py /home/vm1/Desktop/ncsu-ip-p1/files/A_10kB
   ```

   When the seeder starts, it will display a magnet link that looks like:
   ```
   magnet:?xt=urn:btih:<hash>&dn=<filename>&tr=<tracker_url>
   ```
   Copy this magnet link for use with the clients.

2. **Start the Clients on VM2, VM3, and VM4**:
   
   For each file size, use the appropriate number of repetitions:
   - A_10kB: 333 repetitions
   - A_100kB: 33 repetitions
   - A_1MB: 3 repetitions
   - A_10MB: 1 repetition

   Run this command on each client VM (VM2, VM3, VM4):
   ```bash
   # General format:
   python bitTorrent/client.py "<magnet_link>" <repetitions>
   
   # Example for A_10kB with 333 repetitions:
   python bitTorrent/client.py "magnet:?xt=urn:btih:2a4a8f6b6ee266ea20cbcf1c1f148a82622d6285&dn=A_10kB&tr=udp://tracker.opentrackr.org:1337" 333
   
   # Example for A_100kB with 33 repetitions:
   python bitTorrent/client.py "magnet:?xt=urn:btih:a636e03b04c06aca1b77d18421907cc3caf397a7&dn=A_100kB&tr=udp://tracker.opentrackr.org:1337" 33
   
   # Example for A_1MB with 3 repetitions:
   python bitTorrent/client.py "magnet:?xt=urn:btih:d582bfe87f63815d66cf9b24acdf54c2048031ae&dn=A_1MB&tr=udp://tracker.opentrackr.org:1337" 3
   
   # Example for A_10MB with 1 repetition:
   python bitTorrent/client.py "magnet:?xt=urn:btih:c5ad84a08ee85f37679e89fdd12591eaae9a85fb&dn=A_10MB&tr=udp://tracker.opentrackr.org:1337" 1
   ```

   **Note**: Try to start all three client VMs at approximately the same time to ensure they can participate together.

3. **Collecting Results**:
   - The seeder will automatically generate result files in the format: `<timestamp>_seeder_metrics.json`
   - For final analysis, use `results_<fileSize>_from_vm1_bitTorrent.json` files

### Analyze Results

After running all experiments, collect all JSON result files from all machines and place them in the project root directory. Then run the analysis script:

```bash
python analyze.py
```

This will generate an Excel file (`results.xlsx`) with the compiled results.

## BitTorrent Tracker Details
The BitTorrent protocol requires a tracker to coordinate communication between peers. In this implementation:

- We use OpenTracker's UDP protocol (udp://tracker.opentrackr.org:1337)
- The tracker helps peers discover each other in the swarm
When the seeder creates a torrent, it registers with the tracker and gets a unique info hash
- Clients connect to the tracker using the magnet link, which contains:

 - The info hash (xt=urn:btih:<hash>)
 - The file name (dn=<filename>)
 - The tracker URL (tr=<tracker_url>)
