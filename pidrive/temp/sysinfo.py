# pidrive/sysinfo.py

def get_system_info(client) -> dict:
    """
    Gather system info from the Pi:
      - RAM (total/used/available) from /proc/meminfo
      - Mount usage from df (bytes)
      - Block devices (labels/UUIDs/mounts) from lsblk (JSON)
      - Include mergerfs pool if present (fuse mount)
    Return a structured dict ready to JSONify.
    """
    import json
    import re

    # 1) RAM: parse /proc/meminfo (kB -> bytes)
    meminfo_out, _, _ = client._exec("cat /proc/meminfo")
    mem_kb = {}
    for line in meminfo_out.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        m = re.search(r"(\d+)\s*kB", v)
        if m:
            mem_kb[k.strip()] = int(m.group(1))
    ram_total = mem_kb.get("MemTotal", 0) * 1024
    ram_available = mem_kb.get("MemAvailable", 0) * 1024
    ram_used = max(ram_total - ram_available, 0)

    # 2) Mount usage: df in bytes for clean calculations
    df_cmd = r"df -B1 --output=source,fstype,size,used,avail,target | tail -n +2"
    df_out, _, _ = client._exec(df_cmd)
    mount_rows = []
    for line in df_out.splitlines():
        parts = line.split()
        if len(parts) < 6:
            # Some mountpoints may contain spaces; re-join the tail
            source, fstype, size, used, avail = parts[:5]
            target = " ".join(parts[5:])
        else:
            source, fstype, size, used, avail, target = parts[:6]
        try:
            size_i = int(size)
            used_i = int(used)
            avail_i = int(avail)
        except ValueError:
            size_i = used_i = avail_i = 0
        mount_rows.append({
            "source": source,
            "fstype": fstype,
            "size_bytes": size_i,
            "used_bytes": used_i,
            "avail_bytes": avail_i,
            "mountpoint": target
        })

    # 3) Block devices with labels/UUIDs as JSON
    lsblk_cmd = "lsblk -J -b -o NAME,TYPE,FSTYPE,LABEL,UUID,SIZE,MOUNTPOINT"
    lsblk_out, lsblk_err, lsblk_code = client._exec(lsblk_cmd)
    try:
        blk = json.loads(lsblk_out)  # {'blockdevices': [...]}
    except Exception:
        blk = {"error": "lsblk_parse_failed", "raw": lsblk_out, "stderr": lsblk_err, "code": lsblk_code}

    # Quick lookups to enrich devices with usage
    by_target = {m["mountpoint"]: m for m in mount_rows if m.get("mountpoint")}
    drives = []

    def walk(nodes):
        for n in nodes:
            entry = {
                "name": n.get("name"),
                "type": n.get("type"),
                "fstype": n.get("fstype"),
                "label": n.get("label"),
                "uuid": n.get("uuid"),
                "size_bytes": int(n.get("size", 0) or 0),
                "mountpoint": n.get("mountpoint"),
            }
            mp = entry["mountpoint"]
            if mp and mp in by_target:
                usage = by_target[mp]
                entry.update({
                    "total_bytes": usage["size_bytes"],
                    "used_bytes": usage["used_bytes"],
                    "avail_bytes": usage["avail_bytes"],
                })
            drives.append(entry)
            if "children" in n and isinstance(n["children"], list):
                walk(n["children"])

    if isinstance(blk, dict) and "blockdevices" in blk:
        walk(blk["blockdevices"])

    # Add FUSE/mergerfs mounts that lsblk doesn't list as block devices
    for m in mount_rows:
        if m["fstype"].startswith("fuse") and not any(d.get("mountpoint") == m["mountpoint"] for d in drives):
            drives.append({
                "name": m["source"], "type": "fuse", "fstype": m["fstype"],
                "label": None, "uuid": None, "size_bytes": m["size_bytes"],
                "mountpoint": m["mountpoint"],
                "total_bytes": m["size_bytes"], "used_bytes": m["used_bytes"], "avail_bytes": m["avail_bytes"],
            })

    # Identify microSD partitions (typical mmcblk0p1/p2)
    microsd = [d for d in drives if (d.get("name") or "").startswith("mmcblk0p")]

    # Helper to format bytes → GiB
    def to_gb(b):
        return round(b / (1024 ** 3), 2) if b else 0.0

    def percent(used, total):
        return round((used / total) * 100, 1) if total else 0.0

    # Build concise drive list (ignore tmpfs/dev)
    drive_summary = []
    for d in drives:
        if d.get("fstype") in (None, "devtmpfs", "tmpfs"):
            continue
        if not d.get("mountpoint"):
            continue
        # Skip internal microSD partitions
        if d.get("name", "").startswith("mmcblk"):
            continue
        total = d.get("total_bytes") or d.get("size_bytes") or 0
        used = d.get("used_bytes", 0)
        avail = d.get("avail_bytes", 0)
        drive_summary.append({
            "label": d.get("label") or d.get("name"),
            "mountpoint": d.get("mountpoint"),
            "fstype": d.get("fstype"),
            "total_gb": to_gb(total),
            "used_gb": to_gb(used),
            "free_gb": to_gb(avail),
            "used_percent": percent(used, total)
        })
    drive_summary = sorted(drive_summary, key=lambda x: x["mountpoint"])

    # MicroSD summary (boot + root)
    microsd_summary = {}
    for d in drives:
        if d.get("label") == "rootfs":
            microsd_summary["root_total_gb"] = to_gb(d.get("total_bytes"))
            microsd_summary["root_used_gb"] = to_gb(d.get("used_bytes"))
        elif d.get("label") == "bootfs":
            microsd_summary["boot_total_gb"] = to_gb(d.get("total_bytes"))
            microsd_summary["boot_used_gb"] = to_gb(d.get("used_bytes"))

    return {
        "ram": {
            "total_gb": to_gb(ram_total),
            "used_gb": to_gb(ram_used),
            "free_gb": to_gb(ram_available),
            "used_percent": percent(ram_used, ram_total),
        },
        "drives": drive_summary,
        "microsd": microsd_summary
    }