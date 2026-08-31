import wmi
import pythoncom


def _decode_product_key(digital_product_id):
    """
    Decodifica o valor binário DigitalProductId do registro do Windows para a
    chave de produto no formato XXXXX-XXXXX-XXXXX-XXXXX-XXXXX. Este é o mesmo
    algoritmo público usado por diversas ferramentas de auditoria de licença.
    """
    key_offset = 52
    is_win8_or_later = (digital_product_id[66] // 6) & 1
    digital_product_id[66] = (digital_product_id[66] & 0xF7) | ((is_win8_or_later & 2) * 4)

    chars = "BCDFGHJKMPQRTVWXY2346789"
    key_output = ""
    last = 0
    for i in range(24, -1, -1):
        current = 0
        for j in range(14, -1, -1):
            current = current * 256
            current += digital_product_id[key_offset + j]
            digital_product_id[key_offset + j] = current // 24
            current = current % 24
        key_output = chars[current] + key_output
        last = current

    if is_win8_or_later:
        # Em Windows 8+/10/11, o caractere na posição 0 apenas guardava a
        # marcação de edição N; ele é descartado e o "N" é reinserido na
        # posição indicada por `last`, mantendo os 25 caracteres da chave.
        remainder = key_output[1:]
        key_output = remainder[:last] + "N" + remainder[last:]

    return "-".join(key_output[i:i + 5] for i in range(0, len(key_output), 5))


def get_product_key(conn):
    """Tenta obter a chave do Windows via registro (StdRegProv) e, se falhar,
    via SoftwareLicensingService (funciona para chaves OEM embutidas na BIOS)."""
    try:
        std_reg = conn.StdRegProv
        HKEY_LOCAL_MACHINE = 0x80000002
        path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        _, value = std_reg.GetBinaryValue(HKEY_LOCAL_MACHINE, path, "DigitalProductId")
        if value:
            return _decode_product_key(list(value))
    except Exception:
        pass

    try:
        for svc in conn.SoftwareLicensingService():
            if svc.OA3xOriginalProductKey:
                return svc.OA3xOriginalProductKey
    except Exception:
        pass

    return "Não disponível"


def collect_machine_info(ip, username, password, domain=None):
    """Conecta via WMI em `ip` e retorna um dicionário com as informações da máquina."""
    pythoncom.CoInitialize()
    try:
        full_user = f"{domain}\\{username}" if domain else username
        conn = wmi.WMI(computer=ip, user=full_user, password=password)

        cs = conn.Win32_ComputerSystem()[0]
        os_info = conn.Win32_OperatingSystem()[0]
        bios = conn.Win32_BIOS()[0]
        try:
            product = conn.Win32_ComputerSystemProduct()[0]
        except Exception:
            product = None

        cpus = [c.Name.strip() for c in conn.Win32_Processor()]

        disks = []
        for d in conn.Win32_LogicalDisk(DriveType=3):  # 3 = discos locais
            size_gb = round(int(d.Size) / (1024 ** 3), 2) if d.Size else 0
            free_gb = round(int(d.FreeSpace) / (1024 ** 3), 2) if d.FreeSpace else 0
            disks.append(
                {
                    "letra": d.DeviceID,
                    "tamanho_gb": size_gb,
                    "livre_gb": free_gb,
                    "sistema_arquivos": d.FileSystem,
                }
            )

        networks = []
        for nic in conn.Win32_NetworkAdapterConfiguration(IPEnabled=True):
            networks.append(
                {
                    "descricao": nic.Description,
                    "ip": nic.IPAddress[0] if nic.IPAddress else None,
                    "mascara": nic.IPSubnet[0] if nic.IPSubnet else None,
                    "gateway": nic.DefaultIPGateway[0] if nic.DefaultIPGateway else None,
                    "mac": nic.MACAddress,
                    "dns": list(nic.DNSServerSearchOrder) if nic.DNSServerSearchOrder else [],
                }
            )

        ram_total_gb = round(int(cs.TotalPhysicalMemory) / (1024 ** 3), 2)
        ram_free_gb = round(int(os_info.FreePhysicalMemory) / (1024 ** 2), 2)  # KB -> GB

        product_key = get_product_key(conn)

        return {
            "ip": ip,
            "hostname": cs.Name,
            "os_name": os_info.Caption,
            "os_version": os_info.Version,
            "manufacturer": cs.Manufacturer,
            "model": cs.Model,
            "serial_number": bios.SerialNumber or (product.IdentifyingNumber if product else ""),
            "cpu": ", ".join(cpus),
            "ram_total_gb": ram_total_gb,
            "ram_free_gb": ram_free_gb,
            "disks_json": disks,
            "network_json": networks,
            "product_key": product_key,
            "status": "online",
        }
    finally:
        pythoncom.CoUninitialize()
