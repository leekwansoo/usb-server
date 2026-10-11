from usbx import usb

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


if __name__ == "__main__":
    for d in list_usb_devices():
        print("---- USB Device ----")
        for k, v in d.items():
            print(f"{k}: {v}")
        print()
