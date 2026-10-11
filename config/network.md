## Terminal type

본 시스템은 Terminal Type에 따라 각각의 IO Port를 Assign하고, 해당 Port에 적합한 Protocol Stack으로 Both-way 데이터를 교환한다."

Wi-Fi Terminal: IO = TCP/IP Socket, Protocol = Tapo API / Kasa
Zigbee Terminal: IO = USB Serial (COM3), Protocol = Zigbee Z-Stack + MQTT
USB Terminal: IO = USB Serial (COM4), Protocol = Custom Serial (pyserial)
BLE Terminal: IO = Bluetooth MAC, Protocol = GATT (bleak, Notify/Write)
Camera Terminal: IO = RTSP URL, Protocol = RTSP/ONVIF

이렇게 설계하면 새로운 Terminal Type이 추가되어도 ports.yaml에 한 줄만 추가하면 되고, Dashboard 코드는 전혀 수정할 필요가 없습니다. 확장 가능한 Gateway Architecture입니다.