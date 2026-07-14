import serial
import serial.tools.list_ports
import time
import logging
import threading
import subprocess
import re
import tempfile
import os
import socket
from typing import Optional, Callable, List, Dict
from src.config.settings import MODEM_PORT, MODEM_BAUD
from src.services.supabase_service import SupabaseService
from src.models.schemas import StaffAssignment

logger = logging.getLogger(__name__)


def _run_powershell(script: str, timeout: int = 10) -> str:
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as f:
            f.write(script)
            tmp_path = f.name
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tmp_path],
            capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.stdout
    except Exception as e:
        logger.warning(f"PowerShell script failed: {e}")
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


class BluetoothScanner:
    SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"

    def __init__(self):
        self._scanning = False

    def scan_devices(self) -> List[Dict[str, str]]:
        raw_devices = self._get_all_bluetooth_devices()
        real_devices = self._filter_real_devices(raw_devices)
        com_ports = self._get_bluetooth_com_ports()
        devices_with_ports = self._map_devices_to_com_ports(real_devices, com_ports)
        return devices_with_ports

    def _get_all_bluetooth_devices(self) -> List[Dict[str, str]]:
        devices = []
        script = """
Get-PnpDevice -Class Bluetooth -Status OK -ErrorAction SilentlyContinue |
Select-Object FriendlyName, InstanceId |
ForEach-Object {
    $n = $_.FriendlyName.Trim()
    $i = $_.InstanceId.Trim()
    if ($n -and $i) { Write-Output ($n + '|||' + $i) }
}
"""
        output = _run_powershell(script)
        for line in output.strip().split("\n"):
            line = line.strip()
            if "|||" in line:
                name, instance_id = line.split("|||", 1)
                devices.append({"name": name.strip(), "instance_id": instance_id.strip()})
        return devices

    def _filter_real_devices(self, devices: List[Dict[str, str]]) -> List[Dict[str, str]]:
        real = []
        seen_macs = set()

        for dev in devices:
            name = dev["name"]
            instance_id = dev["instance_id"]

            if "USB\\VID_" in instance_id:
                continue

            if "\\{" in instance_id and "_VID&" in instance_id:
                continue

            mac = self._extract_mac(instance_id)
            if not mac:
                continue

            if mac in seen_macs:
                continue
            seen_macs.add(mac)

            real.append({
                "name": name,
                "instance_id": instance_id,
                "mac": mac,
                "port": None,
                "type": self._classify_device(name, instance_id),
            })

        real.sort(key=lambda d: (0 if d["type"] == "phone" else 1 if d["type"] == "tablet" else 2))
        return real

    def _extract_mac(self, instance_id: str) -> Optional[str]:
        match = re.search(r"DEV_([0-9A-Fa-f]{12,})", instance_id)
        if match:
            return match.group(1).upper()
        match = re.search(r"BLUETOOTHDEVICE_([0-9A-Fa-f]{12,})", instance_id)
        if match:
            return match.group(1).upper()
        return None

    def _classify_device(self, name: str, instance_id: str) -> str:
        name_lower = name.lower()
        if any(kw in name_lower for kw in ["phone", "s24", "s23", "galaxy", "iphone", "pixel", "oneplus", "xiaomi", "huawei", "oppo", "vivo"]):
            return "phone"
        if any(kw in name_lower for kw in ["tab", "pad", "ipad", "tablet"]):
            return "tablet"
        if any(kw in name_lower for kw in ["watch", "band", "fit"]):
            return "wearable"
        if any(kw in name_lower for kw in ["buds", "headset", "headphone", "earbuds", "speaker", "mp3", "audio"]):
            return "audio"
        if any(kw in name_lower for kw in ["printer", "keyboard", "mouse", "controller"]):
            return "accessory"
        return "device"

    def _get_bluetooth_com_ports(self) -> List[Dict[str, str]]:
        com_ports = []
        script = """
Get-PnpDevice -Class Ports -Status OK -ErrorAction SilentlyContinue |
Select-Object FriendlyName, InstanceId |
ForEach-Object {
    $n = $_.FriendlyName.Trim()
    $i = $_.InstanceId.Trim()
    if ($n -and $i) { Write-Output ($n + '|||' + $i) }
}
"""
        output = _run_powershell(script)
        for line in output.strip().split("\n"):
            line = line.strip()
            if "|||" in line:
                name, instance_id = line.split("|||", 1)
                if "bluetooth" in name.lower() or "bth" in instance_id.lower():
                    port_match = re.search(r"\(COM(\d+)\)", name)
                    port_num = port_match.group(1) if port_match else None
                    mac = self._extract_mac_from_com(instance_id)
                    com_ports.append({
                        "name": name.strip(),
                        "instance_id": instance_id.strip(),
                        "port": f"COM{port_num}" if port_num else None,
                        "mac": mac,
                    })

        if not com_ports:
            for p in serial.tools.list_ports.comports():
                desc = (p.description or "").lower()
                if "bluetooth" in desc or "bth" in desc.lower():
                    com_ports.append({
                        "name": p.description,
                        "instance_id": p.hwid or "",
                        "port": p.device,
                        "mac": None,
                    })
        return com_ports

    def _extract_mac_from_com(self, instance_id: str) -> Optional[str]:
        match = re.search(r"&(?:[0-9A-Fa-f]{12,})(?:_C[0-9A-Fa-f]+)?$", instance_id, re.IGNORECASE)
        if match:
            raw = match.group(0).lstrip("&")
            raw = re.sub(r"_C[0-9A-Fa-f]+$", "", raw, flags=re.IGNORECASE)
            if len(raw) >= 12:
                return raw[:12].upper()

        match = re.search(r"([0-9A-Fa-f]{12})", instance_id.replace("-", ""))
        if match:
            raw = match.group(1)
            if len(raw) >= 12 and raw != "000000000000":
                return raw[:12].upper()
        return None

    def _map_devices_to_com_ports(self, devices: List[Dict[str, str]], com_ports: List[Dict[str, str]]) -> List[Dict[str, str]]:
        for dev in devices:
            dev_mac = dev.get("mac", "")
            for cp in com_ports:
                cp_mac = cp.get("mac", "")
                if dev_mac and cp_mac and dev_mac == cp_mac:
                    dev["port"] = cp["port"]
                    dev["com_port_name"] = cp["name"]
                    break

        result = []
        for dev in devices:
            if dev["port"]:
                dev["type"] = "phone_ready" if dev["type"] == "phone" else "device_ready"
            result.append(dev)

        result.sort(key=lambda d: (
            0 if d.get("port") and d["type"] == "phone_ready" else
            1 if d.get("port") else
            2 if d["type"] == "phone" else
            3 if d["type"] == "tablet" else 4
        ))
        return result

    def find_com_port_for_device(self, device_id: str) -> Optional[str]:
        ports = serial.tools.list_ports.comports()
        device_id_lower = device_id.lower()
        for port in ports:
            if port.hwid and device_id_lower in port.hwid.lower():
                return port.device
        script = f"""
Get-PnpDevice -InstanceId '{device_id}' -ErrorAction SilentlyContinue |
Get-PnpDeviceProperty -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue |
ForEach-Object {{ $_.Data }}
"""
        parent_id = _run_powershell(script, timeout=5).strip()
        if parent_id:
            for port in ports:
                if port.hwid and parent_id.lower() in port.hwid.lower():
                    return port.device
        for port in ports:
            desc_lower = (port.description or "").lower()
            if any(kw in desc_lower for kw in ["bluetooth", "bt", "spp", "serial"]):
                return port.device
        return None

    def get_all_bluetooth_com_ports(self) -> List[Dict[str, str]]:
        return self._get_bluetooth_com_ports()

    def open_bluetooth_settings(self):
        try:
            subprocess.Popen(["start", "ms-settings:bluetooth"], shell=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            try:
                subprocess.Popen(["control", "bthprops.cpl"], shell=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e:
                logger.warning(f"Could not open Bluetooth settings: {e}")


class GSMModem:
    def __init__(self, port: str = MODEM_PORT, baud: int = MODEM_BAUD):
        self.port = port
        self.baud = baud
        self.serial_conn = None
        self.tcp_socket = None
        self.is_connected = False
        self._listener_thread = None
        self._running = False
        self._lock = threading.Lock()
        self._callbacks = {
            "on_message": [],
            "on_call": [],
            "on_status": [],
        }
        self._auto_reconnect = False
        self._reconnect_thread = None
        self._reconnect_delay = 3
        self._device_id = None
        self._connection_type = "serial"
        self._tcp_host = None
        self._tcp_port = None

    def connect(self) -> bool:
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=2,
                write_timeout=2
            )
            time.sleep(2)
            resp = self._send_at("AT")
            if "OK" not in resp:
                logger.error("Modem not responding to AT")
                return False
            self._send_at("ATE0")
            self._send_at("AT+CMGF=1")
            self._send_at("AT+CNMI=2,2,0,0,0")
            self._send_at("AT+CLIP=1")
            self._send_at("AT+COLP=1")
            self._send_at("AT+CSMS=1")
            self._send_at("AT+CMEE=1")
            self.is_connected = True
            self._running = True
            self._start_listener()
            return True
        except Exception as e:
            logger.error(f"Modem connection failed: {e}")
            return False

    def connect_wireless(self, device_id: str = None, baud: int = None) -> bool:
        self._connection_type = "bluetooth"
        self._device_id = device_id
        self._auto_reconnect = True
        if baud:
            self.baud = baud

        scanner = BluetoothScanner()

        if device_id:
            com_port = scanner.find_com_port_for_device(device_id)
            if com_port:
                self.port = com_port
            else:
                bt_ports = scanner.get_all_bluetooth_com_ports()
                if bt_ports:
                    self.port = bt_ports[0]["port"]
                else:
                    all_ports = serial.tools.list_ports.comports()
                    for p in all_ports:
                        desc = (p.description or "").lower()
                        if any(kw in desc for kw in ["bluetooth", "bt", "spp", "serial", "comm"]):
                            self.port = p.device
                            break
                    if not self.port or self.port == MODEM_PORT:
                        logger.error("No Bluetooth COM port found for device")
                        return False

        success = self.connect()
        if success:
            self._start_reconnect_monitor()
        return success

    def connect_tcp(self, host: str, port: int = 8080) -> bool:
        self._connection_type = "tcp"
        self._tcp_host = host
        self._tcp_port = port
        self._auto_reconnect = True
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.settimeout(10)
            self.tcp_socket.connect((host, port))
            self.tcp_socket.settimeout(None)
            time.sleep(1)
            resp = self._send_at("AT")
            if "OK" not in resp:
                logger.error("TCP modem not responding to AT")
                self.tcp_socket.close()
                self.tcp_socket = None
                return False
            self._send_at("ATE0")
            self._send_at("AT+CMGF=1")
            self._send_at("AT+CNMI=2,2,0,0,0")
            self._send_at("AT+CLIP=1")
            self._send_at("AT+COLP=1")
            self._send_at("AT+CSMS=1")
            self._send_at("AT+CMEE=1")
            self.is_connected = True
            self._running = True
            self._start_listener()
            self._start_reconnect_monitor()
            return True
        except Exception as e:
            logger.error(f"TCP connection failed: {e}")
            if self.tcp_socket:
                self.tcp_socket.close()
                self.tcp_socket = None
            return False

    def _start_reconnect_monitor(self):
        def monitor():
            while self._auto_reconnect and self._running:
                time.sleep(5)
                if not self.is_connected and self._auto_reconnect:
                    logger.info("Connection lost, attempting reconnect...")
                    for attempt in range(5):
                        if not self._auto_reconnect:
                            break
                        try:
                            if self._connection_type == "tcp":
                                if self.tcp_socket:
                                    try:
                                        self.tcp_socket.close()
                                    except Exception:
                                        pass
                                self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                self.tcp_socket.settimeout(10)
                                self.tcp_socket.connect((self._tcp_host, self._tcp_port))
                                self.tcp_socket.settimeout(None)
                            else:
                                if self.serial_conn and self.serial_conn.is_open:
                                    self.serial_conn.close()
                                self.serial_conn = serial.Serial(
                                    port=self.port,
                                    baudrate=self.baud,
                                    timeout=2,
                                    write_timeout=2
                                )
                            time.sleep(2)
                            resp = self._send_at("AT")
                            if "OK" in resp:
                                self._send_at("ATE0")
                                self._send_at("AT+CMGF=1")
                                self._send_at("AT+CNMI=2,2,0,0,0")
                                self._send_at("AT+CLIP=1")
                                self._send_at("AT+COLP=1")
                                self.is_connected = True
                                self._running = True
                                self._start_listener()
                                logger.info("Reconnected successfully")
                                for cb in self._callbacks["on_status"]:
                                    cb({"status": "reconnected"})
                                break
                        except Exception as e:
                            logger.warning(f"Reconnect attempt {attempt+1} failed: {e}")
                            time.sleep(self._reconnect_delay)

        self._reconnect_thread = threading.Thread(target=monitor, daemon=True)
        self._reconnect_thread.start()

    def disconnect(self):
        self._auto_reconnect = False
        self._running = False
        self.is_connected = False
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            self._reconnect_thread.join(timeout=3)
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=3)
        if self._connection_type == "tcp" and self.tcp_socket:
            try:
                self.tcp_socket.close()
            except Exception:
                pass
            self.tcp_socket = None
        elif self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

    def _send_at(self, command: str, wait: float = 1.0) -> str:
        with self._lock:
            try:
                if self._connection_type == "tcp":
                    if not self.tcp_socket:
                        return ""
                    self.tcp_socket.sendall(f"{command}\r\n".encode())
                    time.sleep(wait)
                    response = ""
                    self.tcp_socket.settimeout(2)
                    while True:
                        try:
                            chunk = self.tcp_socket.recv(4096).decode(errors='ignore')
                            if not chunk:
                                break
                            response += chunk
                        except socket.timeout:
                            break
                    self.tcp_socket.settimeout(None)
                    return response.strip()
                else:
                    if not self.serial_conn or not self.serial_conn.is_open:
                        return ""
                    self.serial_conn.reset_input_buffer()
                    self.serial_conn.write(f"{command}\r\n".encode())
                    time.sleep(wait)
                    response = ""
                    while self.serial_conn.in_waiting:
                        chunk = self.serial_conn.read(self.serial_conn.in_waiting).decode(errors='ignore')
                        response += chunk
                    return response.strip()
            except Exception as e:
                logger.error(f"AT command failed: {e}")
                return ""

    def send_sms(self, phone: str, message: str) -> bool:
        try:
            self._send_at(f'AT+CMGS="{phone}"', wait=1.0)
            time.sleep(0.5)
            with self._lock:
                if self._connection_type == "tcp":
                    self.tcp_socket.sendall(f"{message}\x1a".encode())
                else:
                    self.serial_conn.write(f"{message}\x1a".encode())
            time.sleep(5)
            response = self._read_response()
            return "+CMGS:" in response or "OK" in response
        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return False

    def _read_response(self) -> str:
        response = ""
        try:
            if self._connection_type == "tcp":
                self.tcp_socket.settimeout(2)
                while True:
                    try:
                        chunk = self.tcp_socket.recv(4096).decode(errors='ignore')
                        if not chunk:
                            break
                        response += chunk
                    except socket.timeout:
                        break
                self.tcp_socket.settimeout(None)
            else:
                while self.serial_conn.in_waiting:
                    response += self.serial_conn.read(self.serial_conn.in_waiting).decode(errors='ignore')
        except Exception:
            pass
        return response

    def make_call(self, phone: str) -> bool:
        try:
            response = self._send_at(f"ATD{phone};", wait=2.0)
            return "OK" in response
        except Exception as e:
            logger.error(f"Call failed: {e}")
            return False

    def answer_call(self) -> bool:
        try:
            response = self._send_at("ATA", wait=1.0)
            return "OK" in response
        except Exception as e:
            logger.error(f"Answer failed: {e}")
            return False

    def reject_call(self) -> bool:
        try:
            response = self._send_at("ATH", wait=1.0)
            return "OK" in response
        except Exception as e:
            logger.error(f"Reject failed: {e}")
            return False

    def end_call(self) -> bool:
        return self.reject_call()

    def get_signal_strength(self) -> int:
        try:
            response = self._send_at("AT+CSQ")
            if "+CSQ:" in response:
                part = response.split("+CSQ:")[1].split(",")[0].strip()
                return int(part)
            return 0
        except:
            return 0

    def get_network_info(self) -> Dict[str, str]:
        try:
            response = self._send_at("AT+COPS?", wait=2.0)
            if "+COPS:" in response:
                parts = response.split("+COPS:")[1].split(",")
                return {"operator": parts[2].strip('"').strip(), "mode": parts[0].strip()}
            return {}
        except:
            return {}

    def get_battery_level(self) -> int:
        try:
            response = self._send_at("AT+CBC")
            if "+CBC:" in response:
                parts = response.split("+CBC:")[1].split(",")
                return int(parts[1].strip())
            return 0
        except:
            return 0

    def get_imei(self) -> str:
        try:
            response = self._send_at("AT+CGSN")
            for line in response.split("\n"):
                line = line.strip()
                if line and line != "OK" and not line.startswith("AT"):
                    return line
            return ""
        except:
            return ""

    def get_iccid(self) -> str:
        try:
            response = self._send_at("AT+CCID")
            if "+CCID:" in response:
                return response.split("+CCID:")[1].strip().strip('"')
            return ""
        except:
            return ""

    def get_operator_name(self) -> str:
        try:
            response = self._send_at("AT+COPS?", wait=3.0)
            if "+COPS:" in response:
                parts = response.split("+COPS:")[1].split(",")
                if len(parts) >= 3:
                    return parts[2].strip('"').strip()
            return ""
        except:
            return ""

    def read_sms(self, index: int) -> Optional[Dict]:
        try:
            self._send_at(f"AT+CMGR={index}", wait=1.0)
            response = self._read_response()
            if "+CMGR:" in response:
                lines = response.split("\n")
                header = lines[0].split("+CMGR:")[1].strip() if len(lines) > 0 else ""
                body = lines[1].strip() if len(lines) > 1 else ""
                return {"index": index, "header": header, "body": body}
            return None
        except:
            return None

    def list_sms(self) -> List[Dict]:
        try:
            self._send_at("AT+CMGL=\"ALL\"", wait=2.0)
            response = self._read_response()
            messages = []
            for line in response.split("\n"):
                if "+CMGL:" in line:
                    messages.append({"raw": line.strip()})
            return messages
        except:
            return []

    def delete_sms(self, index: int) -> bool:
        try:
            response = self._send_at(f"AT+CMGD={index}")
            return "OK" in response
        except:
            return False

    def delete_all_sms(self) -> bool:
        try:
            response = self._send_at("AT+CMGD=1,4")
            return "OK" in response
        except:
            return False

    def _start_listener(self):
        def listener():
            buffer = ""
            while self._running:
                try:
                    chunk = ""
                    if self._connection_type == "tcp" and self.tcp_socket:
                        self.tcp_socket.settimeout(0.5)
                        try:
                            chunk = self.tcp_socket.recv(4096).decode(errors='ignore')
                        except socket.timeout:
                            pass
                        except Exception:
                            if self._running:
                                self.is_connected = False
                            break
                    elif self.serial_conn and self.serial_conn.in_waiting:
                        chunk = self.serial_conn.read(self.serial_conn.in_waiting).decode(errors='ignore')

                    if chunk:
                        buffer += chunk
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if line.startswith("+CMT:"):
                                parts = line.split(",")
                                phone = parts[0].split('"')[1] if '"' in parts[0] else ""
                                for cb in self._callbacks["on_message"]:
                                    cb({"phone": phone, "text": "", "status": "received"})
                            elif line.startswith("+CLIP:"):
                                phone = line.split('"')[1] if '"' in line else ""
                                for cb in self._callbacks["on_call"]:
                                    cb({"phone": phone, "status": "incoming"})
                            elif line.startswith("RING"):
                                for cb in self._callbacks["on_call"]:
                                    cb({"phone": "", "status": "ringing"})
                            elif line.startswith("NO CARRIER") or line.startswith("BUSY") or line.startswith("NO ANSWER"):
                                for cb in self._callbacks["on_call"]:
                                    cb({"phone": "", "status": "ended"})
                    time.sleep(0.05)
                except Exception as e:
                    if self._running:
                        logger.error(f"Listener error: {e}")

        self._listener_thread = threading.Thread(target=listener, daemon=True)
        self._listener_thread.start()

    def on(self, event_type: str, callback: Callable):
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)

    @staticmethod
    def list_ports() -> List[str]:
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    @staticmethod
    def scan_modems() -> List[Dict[str, str]]:
        ports = serial.tools.list_ports.comports()
        results = []
        for p in ports:
            info = {"port": p.device, "description": p.description, "manufacturer": p.manufacturer or ""}
            results.append(info)
        return results


class SMSService:
    def __init__(self, assignment: StaffAssignment):
        self.assignment = assignment
        self.supabase = SupabaseService()
        self.modem = GSMModem()
        self.is_connected = False
        self._callbacks = {
            "on_message": [],
            "on_call": [],
            "on_status": [],
        }

    def connect(self, port: str = None, baud: int = None) -> bool:
        if port:
            self.modem.port = port
        if baud:
            self.modem.baud = baud
        self.is_connected = self.modem.connect()
        if self.is_connected:
            self.modem.on("on_message", self._handle_message)
            self.modem.on("on_call", self._handle_call)
            self.modem.on("on_status", self._handle_status)
            self.supabase.update_assignment_status(
                self.assignment.id, "connected",
                {"imei": self.modem.get_imei(), "port": self.modem.port, "network": self.modem.get_operator_name(), "connection_type": "serial"}
            )
        return self.is_connected

    def connect_wireless(self, device_id: str = None, baud: int = None) -> bool:
        self.is_connected = self.modem.connect_wireless(device_id, baud)
        if self.is_connected:
            self.modem.on("on_message", self._handle_message)
            self.modem.on("on_call", self._handle_call)
            self.modem.on("on_status", self._handle_status)
            self.supabase.update_assignment_status(
                self.assignment.id, "connected",
                {"imei": self.modem.get_imei(), "port": self.modem.port, "network": self.modem.get_operator_name(), "connection_type": "bluetooth", "device_id": device_id}
            )
        return self.is_connected

    def connect_tcp(self, host: str, port: int = 8080) -> bool:
        self.is_connected = self.modem.connect_tcp(host, port)
        if self.is_connected:
            self.modem.on("on_message", self._handle_message)
            self.modem.on("on_call", self._handle_call)
            self.modem.on("on_status", self._handle_status)
            self.supabase.update_assignment_status(
                self.assignment.id, "connected",
                {"imei": self.modem.get_imei(), "host": host, "port": port, "network": self.modem.get_operator_name(), "connection_type": "wifi"}
            )
        return self.is_connected

    def disconnect(self):
        self.modem.disconnect()
        self.is_connected = False
        self.supabase.update_assignment_status(self.assignment.id, "disconnected")

    def send_sms(self, phone: str, message: str) -> bool:
        return self.modem.send_sms(phone, message)

    def make_call(self, phone: str) -> bool:
        return self.modem.make_call(phone)

    def answer_call(self) -> bool:
        return self.modem.answer_call()

    def reject_call(self) -> bool:
        return self.modem.reject_call()

    def end_call(self) -> bool:
        return self.modem.end_call()

    def get_signal_strength(self) -> int:
        return self.modem.get_signal_strength()

    def get_network_info(self) -> Dict[str, str]:
        return self.modem.get_network_info()

    def get_battery_level(self) -> int:
        return self.modem.get_battery_level()

    def get_imei(self) -> str:
        return self.modem.get_imei()

    def get_iccid(self) -> str:
        return self.modem.get_iccid()

    def read_sms(self, index: int) -> Optional[Dict]:
        return self.modem.read_sms(index)

    def list_sms(self) -> List[Dict]:
        return self.modem.list_sms()

    def delete_sms(self, index: int) -> bool:
        return self.modem.delete_sms(index)

    def delete_all_sms(self) -> bool:
        return self.modem.delete_all_sms()

    def _handle_message(self, msg):
        for cb in self._callbacks["on_message"]:
            cb(msg)

    def _handle_call(self, call):
        for cb in self._callbacks["on_call"]:
            cb(call)

    def _handle_status(self, status):
        self.is_connected = status.get("status") == "reconnected"
        for cb in self._callbacks["on_status"]:
            cb(status)

    def on(self, event_type: str, callback: Callable):
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
