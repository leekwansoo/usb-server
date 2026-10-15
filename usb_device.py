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

def get_known_product_name(vid, pid):
    return KNOWN_PRODUCTS.get((vid, pid))

def get_product_name(class_code):
    return CLASS_NAMES.get(class_code, 'Other')

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

def list_usb_devices():
    devices = usb.get_devices()
    results = []

    for dev in devices:
        info = {
            "device_type": dev.product,                     # Product name
            "vendor_id": f"0x{dev.vid:04x}",
            "product_id": f"0x{dev.pid:04x}",
            "manufacturer": dev.manufacturer,
            "serial_number": dev.serial,
            "device_version": dev.device_version,
            "interfaces": len(dev.configuration.interfaces),
            "product_name": get_known_product_name(dev.vid, dev.pid)
        }

        # Collect interface class/subclass info
        interface_details = []
        for interface in dev.configuration.interfaces:
            alt = interface.current_alternate
            interface_details.append({
                "class_code": alt.class_code,
                "subclass_code": alt.subclass_code,
                "protocol_code": alt.protocol_code
            })

        info["interface_details"] = interface_details
        results.append(info)

    return results

def list_webcam_devices():
    webcam_devices = []
    devices = list_usb_devices()
    for d in devices:
        if d["device_type"]  != None:
            if "WEBCAM" in d["device_type"] or "CAMERA" in d["device_type"]:
                webcam_devices.append(d)
    return webcam_devices

if __name__ == "__main__":
    for d in list_usb_devices():
        print("---- USB Device ----")
        for k, v in d.items():
            print(f"{k}: {v}")
        print()