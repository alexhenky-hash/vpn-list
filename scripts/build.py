#!/usr/bin/env python3
"""Собирает из vpn.txt списки для AWG-Manager, Happ и INCY.

Без внешних зависимостей (только стандартная библиотека Python 3).

  python3 scripts/build.py data
      -> dist/awg.txt, dist/domains.txt, dist/cidr.txt,
         dist/geosite.dat(+.sha256), dist/geoip.dat(+.sha256)

  python3 scripts/build.py profiles --repo USER/REPO --ref <commit-sha>
      -> dist/happ.json, dist/happ-deeplink.txt,
         dist/incy.json, dist/incy-deeplink.txt
"""
import argparse
import base64
import hashlib
import ipaddress
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "vpn.txt"
DIST = ROOT / "dist"
TAG = "PERSONAL"  # в Happ/INCY используется как geosite:personal / geoip:personal
PROFILE_NAME = "Personal VPN"

# Типы доменов в формате v2ray/xray (router.proto): Plain=0, Regex=1, Domain=2, Full=3
DOMAIN_TYPES = {"keyword": 0, "regexp": 1, "domain": 2, "full": 3}


# ---------- разбор vpn.txt ----------
def parse(path):
    domains, cidrs, errors = [], [], []
    seen = set()
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        # IP / подсеть
        try:
            net = ipaddress.ip_network(line, strict=False)
            key = ("ip", str(net))
            if key not in seen:
                seen.add(key)
                cidrs.append(net)
            continue
        except ValueError:
            pass
        kind, value = "domain", line
        if ":" in line:
            kind, value = line.split(":", 1)
            kind = kind.strip().lower()
            value = value.strip()
            if kind not in DOMAIN_TYPES:
                errors.append(f"строка {n}: неизвестный префикс '{kind}:' в '{raw.strip()}'")
                continue
        if kind != "regexp":
            value = value.lower().lstrip("*").lstrip(".")
            if not value or " " in value or "/" in value:
                errors.append(f"строка {n}: не похоже на домен: '{raw.strip()}'")
                continue
        key = (kind, value)
        if key not in seen:
            seen.add(key)
            domains.append((kind, value))
    return domains, cidrs, errors


# ---------- минимальный кодировщик protobuf ----------
def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def f_varint(num, value):
    return varint(num << 3 | 0) + varint(value)


def f_bytes(num, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return varint(num << 3 | 2) + varint(len(data)) + data


def geosite_dat(domains):
    # Domain{type=1,value=2}; GeoSite{country_code=1,domain=2}; GeoSiteList{entry=1}
    body = f_bytes(1, TAG)
    for kind, value in domains:
        t = DOMAIN_TYPES[kind]
        dom = (f_varint(1, t) if t else b"") + f_bytes(2, value)
        body += f_bytes(2, dom)
    return f_bytes(1, body)


def geoip_dat(cidrs):
    # CIDR{ip=1,prefix=2}; GeoIP{country_code=1,cidr=2}; GeoIPList{entry=1}
    body = f_bytes(1, TAG)
    for net in cidrs:
        body += f_bytes(2, f_bytes(1, net.network_address.packed) + f_varint(2, net.prefixlen))
    return f_bytes(1, body)


def write(name, data):
    p = DIST / name
    if isinstance(data, str):
        data = data.encode("utf-8")
    p.write_bytes(data)
    return p


def stage_data():
    domains, cidrs, errors = parse(SRC)
    if errors:
        print("Ошибки в vpn.txt:\n  " + "\n  ".join(errors), file=sys.stderr)
        sys.exit(1)
    DIST.mkdir(exist_ok=True)
    plain = [v for k, v in domains if k in ("domain", "full")]
    write("domains.txt", "\n".join(plain) + "\n")
    write("cidr.txt", "\n".join(map(str, cidrs)) + "\n")
    write("awg.txt", "\n".join(plain + [str(c) for c in cidrs]) + "\n")
    for name, data in (("geosite.dat", geosite_dat(domains)), ("geoip.dat", geoip_dat(cidrs))):
        write(name, data)
        write(name + ".sha256", hashlib.sha256(data).hexdigest())
    print(f"OK: доменов {len(domains)}, подсетей {len(cidrs)}")


def profile(geosite_url, geoip_url):
    return {
        "Name": PROFILE_NAME,
        "GlobalProxy": "false",          # по умолчанию напрямую, через VPN только список
        "UseChunkFiles": "false",
        "RemoteDns": "8.8.8.8",          # DNS для доменов из списка — через VPN
        "DomesticDns": "77.88.8.8",      # DNS для остальных — российский
        "RemoteDNSType": "DoH",
        "RemoteDNSDomain": "https://8.8.8.8/dns-query",
        "RemoteDNSIP": "8.8.8.8",
        "DomesticDNSType": "DoH",
        "DomesticDNSDomain": "https://77.88.8.8/dns-query",
        "DomesticDNSIP": "77.88.8.8",
        "Geoipurl": geoip_url,
        "Geositeurl": geosite_url,
        "LastUpdated": str(int(time.time())),
        "DnsHosts": {},
        "RouteOrder": "block-proxy-direct",
        "DirectSites": [],
        "DirectIp": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
                     "169.254.0.0/16", "100.64.0.0/10", "fc00::/7", "fe80::/10"],
        "ProxySites": ["geosite:personal"],
        "ProxyIp": ["geoip:personal"],
        "BlockSites": [],
        "BlockIp": [],
        "DomainStrategy": "IPIfNonMatch",
        "FakeDNS": "false",
    }


def stage_profiles(repo, ref):
    cdn = f"https://cdn.jsdelivr.net/gh/{repo}"
    # Happ перекачивает geo-файлы при смене ссылки/LastUpdated -> ссылка с фиксированным коммитом
    happ = profile(f"{cdn}@{ref}/dist/geosite.dat", f"{cdn}@{ref}/dist/geoip.dat")
    # INCY сверяет dist/*.dat.sha256 -> постоянная ссылка на ветку main
    incy = profile(f"{cdn}@main/dist/geosite.dat", f"{cdn}@main/dist/geoip.dat")
    for app, prof in (("happ", happ), ("incy", incy)):
        js = json.dumps(prof, ensure_ascii=False, indent=2)
        write(f"{app}.json", js + "\n")
        b64 = base64.b64encode(json.dumps(prof, ensure_ascii=False, separators=(",", ":")).encode()).decode()
        write(f"{app}-deeplink.txt", f"{app}://routing/onadd/{b64}\n")
    print("OK: профили Happ и INCY")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["data", "profiles"])
    ap.add_argument("--repo")
    ap.add_argument("--ref")
    a = ap.parse_args()
    if a.stage == "data":
        stage_data()
    else:
        if not (a.repo and a.ref):
            ap.error("для profiles нужны --repo и --ref")
        stage_profiles(a.repo, a.ref)
