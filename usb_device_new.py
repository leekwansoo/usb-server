from usbx import usb

# 알려진 VID:PID -> 제품명 백업 DB (장치가 이름을 안 줄 때용)
KNOWN_PRODUCTS = {
    (0x046d, 0x0825): "Logitech C270 HD WEBCAM",
    (0x0bda, 0x0129): "Realtek RTS5129 Card Reader",
    (0x248a, 0x8373): "Samsung Wireless Combo (Keyboard+Mouse Dongle)",
    (0x8087, 0x0026): "Intel AX201 Bluetooth",
}

CLASS_NAMES = {
    1: "Audio",
    3: "HID (키보드/마우스)",
    8: "Mass Storage",
    9: "Hub",
    14: "Video (웹캠)",
    224: "Wireless (Bluetooth/WiFi)",
    255: "Vendor Specific",
}

def safe_get_string(dev, index):
    if not index:
        return None
    try:
        # langid 0x0409 = English (US) 강제하면 한글 윈도우에서 에러 덜 남
        return usb.util.get_string(dev, index, langid=0x0409)
    except Exception:
        try:
            return usb.util.get_string(dev, index)
        except Exception:
            return None

def main():
    devices = list(usb.core.find(find_all=True))
    if not devices:
        print("USB 장치를 찾을 수 없습니다. Zadig/libusb 드라이버나 권한을 확인하세요.")
        return

    for dev in devices:
        manufacturer = safe_get_string(dev, dev.iManufacturer)
        product_str = safe_get_string(dev, dev.iProduct)
        serial = safe_get_string(dev, dev.iSerialNumber)

        vid, pid = dev.idVendor, dev.idProduct
        
        # 1. 장치 자체 문자열 우선, 2. 백업 DB, 3. None
        product_name = product_str or KNOWN_PRODUCTS.get((vid, pid)) or "Unknown"

        print("\n---- USB Device ----")
        print(f"device_type: {product_name}")
        print(f"vendor_id: 0x{vid:04x} (제조사 ID)")
        print(f"product_id: 0x{pid:04x} (제품 ID)")
        print(f"-> VID:PID = {vid:04x}:{pid:04x} 조합으로 제품 식별")
        print(f"manufacturer_string: {manufacturer}")
        print(f"product_string: {product_str}")
        print(f"serial_number: {serial}")
        print(f"device_version: {dev.bcdDevice >> 8}.{dev.bcdDevice & 0xFF:02x}")

        # 인터페이스 정보
        try:
            interfaces = []
            details = []
            for cfg in dev:
                for intf in cfg:
                    interfaces.append(intf.bInterfaceNumber)
                    class_code = intf.bInterfaceClass
                    details.append({
                        'class_code': class_code,
                        'class_name': CLASS_NAMES.get(class_code, 'Other'),
                        'subclass_code': intf.bInterfaceSubClass,
                        'protocol_code': intf.bInterfaceProtocol
                    })
            print(f"interfaces: {len(details)}")
            print(f"interface_details: {details}")
        except Exception as e:
            print(f"interfaces: (구성 정보를 읽을 수 없음: {e})")

if __name__ == "__main__":
    main()
