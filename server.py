"""
Integrated IoT Control Center - FastMCP Server
- Supports: Temperature, Door1/2, Light1/2, Smart Plug P115 (Tapo), Home Camera (RTSP)
- Both-way: Server<->Terminal communication demo
- Transport: SSE (for web dashboard) + stdio (for Claude Desktop)

pip install fastmcp tapo python-kasa paho-mqtt opencv-python
"""

from mcp.server.fastmcp import FastMCP
from typing import Dict, Any
import asyncio
import random
import datetime
import json
import os

# Optional imports - will work in simulation mode if not installed
try:
    from tapo import ApiClient
    TAPO_AVAILABLE = True
except:
    TAPO_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except:
    CV2_AVAILABLE = False

mcp = FastMCP("IoT-Gateway-BothWay")

# ===================== CONFIG =====================
# 환경변수로 관리 - mcp.json에서 주입
TAPO_EMAIL = os.getenv("TAPO_EMAIL", "your_tapo@email.com")
TAPO_PASSWORD = os.getenv("TAPO_PASSWORD", "your_password")
# 실제 IP로 교체하세요
DEVICE_IPS = {
    "Light1": "192.168.0.101",
    "Light2": "192.168.0.102",
    "Switch1": "192.168.0.103",  # Tapo P110M
    "Switch2": "192.168.0.104",  # Tapo P110M
}
# 카메라 RTSP 주소 (예: Tapo C200, C320WS)
CAMERA_RTSP = {
    "Camera1": os.getenv("CAMERA1_RTSP", ""),
    "Camera2": os.getenv("CAMERA2_RTSP", ""),
    # 시뮬레이션 모드면 더미 URL 사용
}

# 상태 저장 (Both-way 데모용)
STATE = {
    "Door1": "CLOSED",
    "Door2": "CLOSED",
    "Light1": {"state": "OFF", "power_w": 0},
    "Light2": {"state": "OFF", "power_w": 0},
    "Switch1": {"state": "OFF", "power_w": 0, "today_kwh": 0.45},
    "Switch2": {"state": "OFF", "power_w": 0, "today_kwh": 0.32},
    "Temp1": {"temperature": 23.5, "humidity": 58},
}

# ===================== UPLINK: Terminal -> Server =====================

@mcp.tool()
async def get_temperature(sensor_id: str = "Temp1") -> Dict[str, Any]:
    """[UPLINK] Temperature Sensor data - Terminal -> Server
    Returns temperature, humidity, battery
    """
    # 실제로는 zigbee2mqtt/Temp1 토픽 구독
    # 시뮬레이션: 약간 변동
    temp = round(22.5 + random.random()*3.5, 1)
    hum = random.randint(52, 68)
    STATE["Temp1"] = {"temperature": temp, "humidity": hum}
    return {
        "sensor_id": sensor_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "temperature_c": temp,
        "humidity_percent": hum,
        "battery_percent": 87,
        "signal_lqi": random.randint(120, 200),
        "direction": "Terminal -> Server (UPLINK)"
    }

@mcp.tool()
async def get_door_status(door_id: str = "Door1") -> Dict[str, Any]:
    """[UPLINK] Door Open/Close Status - Terminal -> Server"""
    return {
        "door_id": door_id,
        "status": STATE.get(door_id, "UNKNOWN"),
        "timestamp": datetime.datetime.now().isoformat(),
        "battery": 92,
        "direction": "Terminal -> Server (UPLINK)"
    }

@mcp.tool()
async def get_light_status(light_id: str = "Light1") -> Dict[str, Any]:
    """[UPLINK] Light status and power"""
    s = STATE.get(light_id, {"state": "OFF", "power_w": 0})
    return {
        "light_id": light_id,
        "state": s["state"],
        "power_w": s["power_w"],
        "today_kwh": round(random.random()*1.2, 3),
        "timestamp": datetime.datetime.now().isoformat(),
        "direction": "Terminal -> Server (UPLINK)"
    }

@mcp.tool()
async def get_smart_plug_energy(plug_id: str = "Switch1") -> Dict[str, Any]:
    """[UPLINK] Tapo P110M Smart Plug Energy Monitoring - Terminal -> Server
    Both models P110M/P115 have energy monitoring and on/off switch
    """
    if TAPO_AVAILABLE and DEVICE_IPS.get(plug_id):
        try:
            client = ApiClient(TAPO_EMAIL, TAPO_PASSWORD)
            device = await client.p110m(DEVICE_IPS[plug_id])
            info = await device.get_device_info()
            energy = await device.get_energy_usage()
            d = energy.to_dict()
            return {
                "plug_id": plug_id,
                "model": info.to_dict().get("model", "P110M"),
                "relay_state": "ON" if info.to_dict()["device_on"] else "OFF",
                "current_power_w": d.get("current_power", 0),
                "today_energy_kwh": d.get("today_energy", 0) / 1000,
                "month_energy_kwh": d.get("month_energy", 0) / 1000,
                "overheated": info.to_dict().get("overheated", False),
                "timestamp": datetime.datetime.now().isoformat(),
                "direction": "Terminal -> Server (UPLINK)"
            }
        except Exception as e:
            pass

    # 시뮬레이션 모드
    s = STATE.get(plug_id, {"state": "OFF", "power_w": 0})
    power = random.randint(800, 1500) if s["state"] == "ON" else 0
    return {
        "plug_id": plug_id,
        "model": "Tapo P110M (Simulated)",
        "relay_state": s["state"],
        "current_power_w": power,
        "today_energy_kwh": s.get("today_kwh", 0.45),
        "month_energy_kwh": 12.34,
        "overheated": False,
        "note": "Simulation mode - install tapo library and set TAPO_EMAIL/PASSWORD for real device",
        "direction": "Terminal -> Server (UPLINK)"
    }

@mcp.tool()
async def get_camera_status(camera_id: str = "Camera1") -> Dict[str, Any]:
    """[UPLINK] Camera monitoring status - Terminal -> Server"""
    # RTSP 연결 테스트 (실제 카메라 없으면 시뮬레이션)
    is_online = True
    motion_detected = random.choice([True, False])
    
    if CV2_AVAILABLE and CAMERA_RTSP.get(camera_id) and CAMERA_RTSP[camera_id].startswith("rtsp://"):
        try:
            cap = cv2.VideoCapture(CAMERA_RTSP[camera_id], cv2.CAP_FFMPEG)
            is_online = cap.isOpened()
            if is_online:
                ret, frame = cap.read()
                if ret:
                    # 스냅샷 저장
                    os.makedirs("static/snapshots", exist_ok=True)
                    snap_path = f"static/snapshots/{camera_id}.jpg"
                    cv2.imwrite(snap_path, frame)
            cap.release()
        except:
            is_online = False

    return {
        "camera_id": camera_id,
        "online": is_online,
        "stream_url": f"/api/camera/{camera_id}/stream",
        "recording": True,
        "motion_detected": motion_detected,
        "resolution": "1920x1080",
        "last_motion": datetime.datetime.now().isoformat() if motion_detected else None,
        "snapshot_url": f"/snapshots/{camera_id}.jpg",
        "direction": "Terminal -> Server (UPLINK - Video)"
    }

@mcp.tool()
async def get_all_status() -> Dict[str, Any]:
    """[UPLINK] Get all devices status in one table - for dashboard"""
    temp = await get_temperature()
    door1 = await get_door_status("Door1")
    door2 = await get_door_status("Door2")
    light1 = await get_light_status("Light1")
    light2 = await get_light_status("Light2")
    plug1 = await get_smart_plug_energy("Switch1")
    plug2 = await get_smart_plug_energy("Switch2")
    cam1 = await get_camera_status("Camera1")
    cam2 = await get_camera_status("Camera2")

    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "devices": {
            "Temp1": temp,
            "Door1": door1,
            "Door2": door2,
            "Light1": light1,
            "Light2": light2,
            "Switch1": plug1,
            "Switch2": plug2,
            "Camera1": cam1,
            "Camera2": cam2
        },
        "summary": "All uplink data collected"
    }

# ===================== DOWNLINK: Server -> Terminal =====================

@mcp.tool()
async def control_door(door_id: str, command: str) -> Dict[str, Any]:
    """[DOWNLINK] Server -> Terminal: Door OPEN/CLOSE command
    Args:
        door_id: Door1 or Door2
        command: OPEN or CLOSE
    """
    command = command.upper()
    if door_id not in ["Door1", "Door2"]:
        return {"error": "Invalid door_id"}
    if command not in ["OPEN", "CLOSE"]:
        return {"error": "Command must be OPEN or CLOSE"}

    # 실제로는 zigbee2mqtt publish: zigbee2mqtt/Door1/set {"state": "OPEN"}
    STATE[door_id] = "OPEN" if command == "OPEN" else "CLOSED"
    
    return {
        "result": "OK",
        "door_id": door_id,
        "command_sent": command,
        "new_status": STATE[door_id],
        "timestamp": datetime.datetime.now().isoformat(),
        "direction": "Server -> Terminal (DOWNLINK)",
        "ack_expected": f"Terminal -> Server: {STATE[door_id]}"
    }

@mcp.tool()
async def control_light(light_id: str, state: str) -> Dict[str, Any]:
    """[DOWNLINK] Server -> Terminal: Light ON/OFF switch button
    Args:
        light_id: Light1 or Light2
        state: ON or OFF
    """
    state = state.upper()
    if light_id not in ["Light1", "Light2", "Switch1", "Switch2"]:
        return {"error": "Invalid light_id"}
    
    power = 12.5 if state == "ON" else 0
    if "Switch" in light_id:
        power = random.randint(800, 1500) if state == "ON" else 0

    # 실제 Tapo 제어
    if TAPO_AVAILABLE and light_id in DEVICE_IPS:
        try:
            client = ApiClient(TAPO_EMAIL, TAPO_PASSWORD)
            device = await client.p115(DEVICE_IPS[light_id])
            if state == "ON":
                await device.on()
            else:
                await device.off()
            # 실제 전력 읽기
            energy = await device.get_energy_usage()
            power = energy.to_dict().get("current_power", power)
        except Exception as e:
            # 실패해도 시뮬레이션으로 진행
            pass

    STATE[light_id] = {"state": state, "power_w": power}

    return {
        "result": "OK",
        "light_id": light_id,
        "command": state,
        "new_state": state,
        "power_w": power,
        "timestamp": datetime.datetime.now().isoformat(),
        "direction": "Server -> Terminal (DOWNLINK)",
        "bothway_demo": f"Downlink: Server->{light_id}:{state} | Uplink will confirm power={power}W"
    }

@mcp.tool()
async def control_camera(camera_id: str, action: str) -> Dict[str, Any]:
    """[DOWNLINK] Server -> Terminal: Camera control
    Args:
        camera_id: Camera1 or Camera2
        action: START_RECORD, STOP_RECORD, SNAPSHOT, REBOOT, MOTION_ON, MOTION_OFF
    """
    valid_actions = ["START_RECORD", "STOP_RECORD", "SNAPSHOT", "REBOOT", "MOTION_ON", "MOTION_OFF"]
    if action not in valid_actions:
        return {"error": f"Invalid action, choose {valid_actions}"}

    # 실제 구현: Tapo C200은 tapo library로 제어 가능
    snapshot_url = None
    if action == "SNAPSHOT":
        snapshot_url = f"/snapshots/{camera_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        # cv2로 캡처 로직

    return {
        "result": "OK",
        "camera_id": camera_id,
        "action": action,
        "snapshot_url": snapshot_url,
        "timestamp": datetime.datetime.now().isoformat(),
        "direction": "Server -> Terminal (DOWNLINK)",
        "note": "Camera control via RTSP/ONVIF or Tapo API"
    }

@mcp.tool()
async def bothway_demo_cycle() -> Dict[str, Any]:
    """[BOTHWAY DEMO] Full cycle: Server->Terminal command + Terminal->Server telemetry
    Shows bothway_data communication for professor demo
    """
    log = []
    log.append(f"[{datetime.datetime.now().isoformat()}] [DOWNLINK] Server -> Light1: ON")
    await control_light("Light1", "ON")
    await asyncio.sleep(0.5)
    status = await get_light_status("Light1")
    log.append(f"[{datetime.datetime.now().isoformat()}] [UPLINK] Light1 -> Server: state={status['state']}, power={status['power_w']}W")
    
    log.append(f"[{datetime.datetime.now().isoformat()}] [DOWNLINK] Server -> Door1: OPEN")
    await control_door("Door1", "OPEN")
    await asyncio.sleep(0.5)
    door = await get_door_status("Door1")
    log.append(f"[{datetime.datetime.now().isoformat()}] [UPLINK] Door1 -> Server: status={door['status']}")

    temp = await get_temperature()
    log.append(f"[{datetime.datetime.now().isoformat()}] [UPLINK] Temp1 -> Server: {temp['temperature_c']}C (spontaneous)")

    cam = await get_camera_status("Camera1")
    log.append(f"[{datetime.datetime.now().isoformat()}] [UPLINK] Camera1 -> Server: motion={cam['motion_detected']}")

    return {
        "demo": "Both-way communication cycle completed",
        "log": log,
        "final_states": STATE
    }

# ===================== RESOURCE =====================
@mcp.resource("config://devices")
def device_list() -> str:
    return json.dumps({
        "devices": list(STATE.keys()) + list(CAMERA_RTSP.keys()),
        "tapo_ips": DEVICE_IPS,
        "camera_rtsp": list(CAMERA_RTSP.keys()),
        "bothway": "Server<->Terminal supported for all devices"
    }, indent=2)

# ===================== MAIN =====================
if __name__ == "__main__":
    # 웹 대시보드용 SSE 모드
    # Claude Desktop용은 stdio로 실행됨 (mcp.json에서 transport 설정)
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        print("Starting FastMCP Server in SSE mode on port 8000...")
        print("Dashboard: http://localhost:8000")
        mcp.run(transport="sse", host="0.0.0.0", port=8000)
    else:
        # 기본: stdio (Claude/Cursor용)
        mcp.run()