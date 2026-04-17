from flask import Flask, request, jsonify
from pyzbar import pyzbar
import cv2, numpy as np, time, datetime
from collections import deque

app = Flask(__name__)
metrics = deque(maxlen=50)
OUTPUT = "scans.txt"
ALLOWED = {"CODE128","EAN13","EAN8","UPCA","UPCE","CODE39","CODE93","I25"}

def decode(img_bytes):
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    codes = pyzbar.decode(img)
    return [b for b in codes if b.type in ALLOWED and b.data]

HTML = '''<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PC Barcode Scanner</title>
<style>
body{font-family:Arial,sans-serif;background:#1a1a1a;color:#fff;padding:20px;text-align:center;margin:0}
#video{width:100%;max-width:640px;border:3px solid #00e5a0;border-radius:10px;margin:10px 0;background:#000}
#canvas{display:none}
.btn{background:#00e5a0;color:#000;padding:12px 24px;border:none;border-radius:5px;font-size:16px;font-weight:bold;margin:5px;cursor:pointer}
.btn:hover{background:#00cc88}
.metrics{background:#2a2a2a;padding:15px;border-radius:8px;margin:15px 0;max-width:640px;margin-left:auto;margin-right:auto}
.row{display:flex;justify-content:space-between;margin:8px 0;font-family:monospace}
.ok{color:#00e5a0}.err{color:#ff6b35}
#result{background:#2a2a2a;padding:15px;border-radius:8px;margin:15px 0;min-height:60px;font-family:monospace;max-width:640px;margin-left:auto;margin-right:auto;word-break:break-all}
.popup{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);display:flex;align-items:center;justify-content:center;z-index:1000;opacity:0;pointer-events:none;transition:opacity 0.3s}
.popup.show{opacity:1;pointer-events:auto}
.popup-box{background:#1a1a1a;padding:30px;border-radius:15px;text-align:center;border:3px solid #00e5a0;max-width:90%;width:400px}
.popup h3{color:#00e5a0;margin:0 0 15px;font-size:24px}
.popup .code{font-size:28px;font-weight:bold;margin:20px 0;color:#fff;word-break:break-all}
.popup .type{color:#888;margin-bottom:20px}
.popup button{background:#00e5a0;color:#000;border:none;padding:12px 30px;border-radius:5px;font-weight:bold;cursor:pointer;font-size:16px}
#status{padding:10px;border-radius:5px;margin:10px 0;display:inline-block}
</style></head><body>
<h1>📷 PC Barcode Scanner</h1>
<video id="video" autoplay playsinline></video>
<canvas id="canvas"></canvas>
<div>
  <button class="btn" onclick="startScan()">▶ STARTin AUTO SCAN</button>
  <button class="btn" onclick="stopScan()">⏸ STOP</button>
  <button class="btn" onclick="scanOnce()">📸 SCAN ONCE</button>
</div>
<div id="status" class="ok">Ready</div>
<div class="metrics">
  <div class="row"><span>⏱️ Last Scan Time:</span><span id="tTime">—</span></div>
  <div class="row"><span>🎯 Success Rate:</span><span id="tRate">—</span></div>
  <div class="row"><span>📦 Total Scans:</span><span id="tTotal">0</span></div>
</div>
<div id="result">Click START AUTO SCAN to begin</div>

<div class="popup" id="popup">
  <div class="popup-box">
    <h3>✅ BARCODE DETECTED!</h3>
    <div class="type" id="popType">—</div>
    <div class="code" id="popCode">—</div>
    <button onclick="closePopup()">CONTINUE</button>
  </div>
</div>

<script>
let video = document.getElementById('video');
let canvas = document.getElementById('canvas');
let ctx = canvas.getContext('2d');
let scanning = false;
let scanInterval = null;
let lastScan = 0;
let totalScans = 0;

// Initialize camera
async function initCamera() {
  const status = document.getElementById('status');

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    status.textContent = '❌ Camera API not supported in this browser';
    status.className = 'err';
    return false;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: "environment" }
      },
      audio: false
    });

    video.srcObject = stream;

    await video.play();

    status.textContent = '✅ Camera Ready';
    status.className = 'ok';

    return true;

  } catch (err) {
    status.textContent = '❌ Camera Error: ' + err.name;
    status.className = 'err';
    console.error(err);
    return false;
  }
}

// Start auto scanning
async function startScan() {
  if (!video.srcObject) {
    const ok = await initCamera();
    if (!ok) return;
  }

  if (scanning) return;

  scanning = true;
  document.getElementById('status').textContent = '🔄 Auto-Scanning...';
  document.getElementById('status').className = 'ok';

  scanInterval = setInterval(scanFrame, 500);
}

// Stop scanning
function stopScan() {
  scanning = false;
  if (scanInterval) clearInterval(scanInterval);
  document.getElementById('status').textContent = '⏸ Paused';
  document.getElementById('status').className = '';
}

// Scan once
async function scanOnce() {
  if (!video.videoWidth) {
    alert('Camera not ready yet');
    return;
  }
  await performScan();
}

// Scan frame
async function scanFrame() {
  if (!scanning || Date.now() - lastScan < 2000) return;
  await performScan();
}

// Perform scan
async function performScan() {
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  ctx.drawImage(video, 0, 0);
  
  canvas.toBlob(async (blob) => {
    if (!blob) return;
    const formData = new FormData();
    formData.append('image', blob, 'scan.jpg');
    
    try {
      const t0 = performance.now();
      const response = await fetch('/scan', { method: 'POST', body: formData });
      const data = await response.json();
      const ms = (performance.now() - t0).toFixed(0);
      
      document.getElementById('tTime').textContent = ms + ' ms';
      totalScans++;
      document.getElementById('tTotal').textContent = totalScans;
      
      if (data.success && data.barcodes[0]) {
        lastScan = Date.now();
        const barcode = data.barcodes[0];
        document.getElementById('tRate').textContent = (data.stats?.success_rate_10 || 100) + '%';
        document.getElementById('result').innerHTML = '<span class="ok">✅ ' + barcode.type + ': ' + barcode.data + '</span>';
        showPopup(barcode.type, barcode.data);
      } else {
        document.getElementById('result').innerHTML = '<span class="err">❌ No barcode found</span>';
      }
    } catch (err) {
      document.getElementById('result').innerHTML = '<span class="err">❌ Error: ' + err.message + '</span>';
    }
  }, 'image/jpeg', 0.8);
}

// Show popup
function showPopup(type, code) {
  document.getElementById('popType').textContent = type;
  document.getElementById('popCode').textContent = code;
  document.getElementById('popup').classList.add('show');
  setTimeout(() => closePopup(), 3000);
}

// Close popup
function closePopup() {
  document.getElementById('popup').classList.remove('show');
}

// Initialize on load
window.addEventListener('load', () => {
  document.getElementById('status').textContent = 'Tap START to enable camera';
});
</script>
</body></html>'''

@app.route('/')
def index(): 
    return HTML

@app.route('/scan', methods=['POST'])
def scan():
    t0 = time.time()
    if 'image' not in request.files: 
        return jsonify({"error":"No image"}), 400
    img = request.files['image'].read()
    codes = decode(img)
    total_ms = (time.time() - t0) * 1000
    success = len(codes) > 0
    result = {"success": success, "total_time_ms": round(total_ms, 1), "barcodes": []}
    
    if success:
        b = codes[0]
        data = b.data.decode("utf-8", errors="ignore").strip()
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        with open(OUTPUT, "a", buffering=1) as f: 
            f.write(f"{ts} | {b.type} | {data} | {total_ms:.1f}ms\n")
        result["barcodes"].append({"type": b.type, "data": data})
    
    metrics.append({"success": success, "time": total_ms})
    if len(metrics) >= 5:
        recent = list(metrics)[-10:]
        result["stats"] = {
            "success_rate_10": round(sum(1 for m in recent if m["success"]) / len(recent) * 100, 1), 
            "avg_time_ms": round(sum(m["time"] for m in recent) / len(recent), 1)
        }
    return jsonify(result)

@app.route('/stats')
def stats():
    if not metrics: 
        return jsonify({"message": "No scans"})
    scans = list(metrics)
    ok = sum(1 for m in scans if m["success"])
    return jsonify({
        "total": len(scans), 
        "success_rate": round(ok/len(scans)*100, 1), 
        "avg_ms": round(sum(m["time"] for m in scans)/len(scans), 1)
    })

if __name__ == '__main__':
    import socket
    ip = socket.gethostbyname(socket.gethostname())

    print("\n" + "="*50)
    print(" PC BARCODE SCANNER")
    print(f" Open on phone: http://{ip}:5000")
    print(" Results: scans.txt")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False)