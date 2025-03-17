# Internet Protocols Project 1

This project implements and compares the performance of HTTP/1.1 and HTTP/2 protocols by transferring files of different sizes between servers and measuring throughput, transfer time, and protocol overhead.

## Setup Instructions

### Install Python packages
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

### Analyze Results

After running all experiments, collect all JSON result files from both machines and place them in the project root directory. Then run the analysis script:

```bash
python analyze.py
```

This will generate an Excel file (`results.xlsx`) with the compiled results.

## Results

The experiment results are saved as JSON files in the format:
- `results_A_from_vm1_http1.json` - Results for downloading A files from VM1 to VM2 using HTTP/1.1
- `results_B_from_vm2_http1.json` - Results for downloading B files from VM2 to VM1 using HTTP/1.1
- `results_A_from_vm1_http2.json` - Results for downloading A files from VM1 to VM2 using HTTP/2
- `results_B_from_vm2_http2.json` - Results for downloading B files from VM2 to VM1 using HTTP/2

The final analysis generates an Excel file (`results.xlsx`) with three sheets:
1. Transfer Time (seconds)
2. Throughput (bits per second)
3. Overhead Ratio
