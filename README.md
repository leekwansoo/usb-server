##  USB/BLE도 Wi-Fi처럼 Both-way로 주고받기.

Wi-Fi(Tapo)는 TCP/IP라 바로 되지만, USB/BLE는 직접 Serial/BLE 프로토콜을 붙여야 합니다.

```code
[Wi-Fi - Tapo P115] : TCP/IP + Tapo API
[USB - Zigbee Dongle]: USB-Serial (COM3) + Zigbee Z-Stack 프로토콜
[BLE - 센서/밴드] : Bluetooth GATT + BLE Characteristics
        ↓
   [FastAPI main.py API Gateway] ← 여기가 통역사 역할
        ↓
   [Web Dashboard] Both-way 동일하게 표시
```

##  2. Device 종류별 필요한 Protocol & Library
### A. USB 장치 (Zigbee Dongle, 아두이노, USB 온습도 센서)
Protocol: USB-Serial (가상 COM 포트)

물리: USB 꽂으면 OS가 COM3 (Windows) / /dev/ttyUSB0 (Linux)로 인식
프로토콜: Serial UART + 각 장치 전용 프로토콜
```text
------------------------------------------------------------
USB 장치         전용 프로토콜             Python 라이브러리
------------------------------------------------------------
ZBDongle-P      Zigbee Z-Stack (TI)     zigbee2mqtt가 통역, 
                                        FastAPI는 MQTT로 받음

아두이노         Custom Serial            pyserial
                (예: TEMP:23.5\n) 

USB 온습도계     HID 또는 Serial          pyserial 또는 hidapi
------------------------------------------------------------
```
### B. BLE 장치 (BLE 온습도 센서, Mi Band, BLE Door 센서)
Protocol: Bluetooth Low Energy GATT

GATT (Generic Attribute Profile) 가 핵심 프로토콜입니다.
장치마다 Service UUID와 Characteristic UUID가 있습니다.
Wi-Fi의 IP처럼, BLE는 UUID로 데이터를 주고받습니다.

```text
------------------------------------------------------------
개념	    Wi-Fi (Tapo)	         BLE
주소	    IP (192.168.0.103)	  MAC (AA:BB:CC:DD:EE:FF)
데이터통로	 TCP 포트	            Characteristic UUID
읽기	    get_energy()	      read_gatt_char(uuid)
쓰기	    device.on()	          write_gatt_char(uuid, data)
자동 보고	     -	             Notify (센서가 자발적으로 쏨)-------------------------------------------------------------
```
필요 라이브러리: bleak (가장 표준, Windows/Linux/Mac 모두 지원)

연결 코드 (BLE 온습도 센서 예시):
```code
# main.py에 추가
from bleak import BleakClient, BleakScanner
import asyncio

# BLE 장치 주소 (스캔으로 찾음)
BLE_TEMP_SENSOR_MAC = "A4:C1:38:12:34:56"
TEMP_CHAR_UUID = "00002a6e-0000-1000-8000-00805f9b34fb" # Temperature Characteristic (표준)

async def ble_uplink_loop():
    """[UPLINK] BLE -> Server : 센서가 Notify로 자발적으로 보냄"""
    def notification_handler(sender, data):
        # data = bytearray로 옴, 예: 온도 23.5°C
        temp = int.from_bytes(data, byteorder='little') / 100.0
        STATE["Temp1"]["temperature"] = temp
        print(f"[UPLINK] BLE Temp Sensor -> Server: {temp}°C")
        # WebSocket으로 Dashboard Push

    async with BleakClient(BLE_TEMP_SENSOR_MAC) as client:
        await client.start_notify(TEMP_CHAR_UUID, notification_handler)
        while True:
            await asyncio.sleep(1)

async def ble_downlink_command(mac: str, char_uuid: str, command: bytes):
    """[DOWNLINK] Server -> BLE : PC가 BLE 장치로 명령"""
    async with BleakClient(mac) as client:
        await client.write_gatt_char(char_uuid, command) # 예: b'\x01' = ON
        print(f"[DOWNLINK] Server -> BLE {mac}: {command.hex()}")

# FastAPI에서 호출
@app.post("/api/control/ble")
async def control_ble(payload: dict):
    # payload: {"mac":"AA:BB:CC:DD:EE:FF", "char_uuid":"...", "command":"01"}
    await ble_downlink_command(payload["mac"], payload["char_uuid"], bytes.fromhex(payload["command"]))
    return {"direction": "Server -> BLE Terminal (DOWNLINK)"}

# 백그라운드 실행
@app.on_event("startup")
async def startup_ble():
    asyncio.create_task(ble_uplink_loop())
```