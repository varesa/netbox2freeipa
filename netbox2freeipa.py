#!/bin/env python3

import ipahttp
import pynetbox
import re
import subprocess

ipa = ipahttp.ipa('treipa2.tre.esav.fi', sslverify='/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem')
ipa.login(
    'autom_netbox2ipa',
    subprocess.check_output(['secret-tool', 'lookup', 'account', 'autom_netbox2ipa']).decode()
)


nb = pynetbox.api(
    'http://netbox-apps.os.tre.esav.fi/',
    token=subprocess.check_output(['secret-tool', 'lookup', 'token', 'autom_netbox2ipa']).decode()
)


def get_zones(ipa):
    reply = ipa.dnszone_find()
    return [zone['idnsname'][0] for zone in reply['result']['result']]


zone_records_cache = {}


def get_zone_records(ipa, zone):
    if zone not in zone_records_cache.keys():
        zone_records_cache[zone] = ipa.dnsrecord_find(zone)['result']['result']
    return zone_records_cache[zone]


def get_addresses(nb):
    addresses = getattr(nb.ipam, 'ip-addresses').all()
    for record in addresses:
        yield {
            "address": str(record.address),
            "status": str(record.status),
            "dns": str(record.dns_name),
            "description": str(record.description),
        }


# borrowed from https://stackoverflow.com/a/2532344/966508
def is_valid_fqdn(hostname):
    if len(hostname) > 255:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1]  # strip exactly one dot from the right, if present
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))


def clean_dns_name(name):
    name = name.strip()
    if not name.endswith('.'):
        name += '.'
    return name


def find_zone(zones, name):
    zone_match = ""
    for zone in zones:
        if name.endswith(zone):
            if len(zone) > len(zone_match):
                zone_match = zone

    if len(zone_match) and len(zone_match) != len(name):
        return zone_match

    return None


zones = get_zones(ipa)

a_records = []
ptr_records = []

for address in get_addresses(nb):
    if address['status'] != "Active":
        continue

    ip, prefix = address['address'].split('/')
    if len(address['dns']):

        name = clean_dns_name(address['dns'])

        if not is_valid_fqdn(name):
            continue

        zone = find_zone(zones, name)
        if not zone:
            continue

        a_records.append((zone, name, ip,))

    if len(address['description']):
        name = clean_dns_name(address['description'])

        if not is_valid_fqdn(name):
            continue

        zone = find_zone(zones, name)
        if not zone:
            continue

        ptr_records.append((ip, name,))

# print(a_records)
# print(ptr_records)


def get_host(fqdn, zone):
    without_zone = fqdn[:fqdn.index(zone)]
    assert without_zone[-1] == '.'
    return without_zone[:-1]


for zone in zones:
    records = get_zone_records(ipa, zone)

    for rec_zone, rec_name, rec_ip in a_records:
        if rec_zone != zone:
            continue
        host = get_host(rec_name, rec_zone)

        for record in records:
            if record['idnsname'][0] == host:
                break
        else:
            print(f"{host} in {zone} is missing a record. Creating now")
            ipa.dnsrecord_add(zone, host, {"arecord": [rec_ip]})

for rec_ip, rec_name in ptr_records:
    prefix_match = ""
    zone_match = ""
    for zone in zones:
        if not zone.endswith('.in-addr.arpa.'):
            continue
        prefix_segments = reversed(zone.split('.')[:-3])
        prefix = '.'.join(prefix_segments) + '.'

        if rec_ip.startswith(prefix) and len(prefix) > len(prefix_match):
            prefix_match = prefix
            zone_match = zone

    if zone_match:
        # print(rec_ip, prefix_match, zone_match)
        recordname_segments = reversed(rec_ip[len(prefix_match):].split('.'))
        recordname = '.'.join(recordname_segments)

        # print(rec_ip, recordname, zone_match)
        records = get_zone_records(ipa, zone_match)
        for record in records:
            if record['idnsname'][0] == recordname:
                # print("Exists: ", rec_name, rec_ip, "-", recordname, zone_match)
                break
        else:
            print("Does not exist: ", rec_name, rec_ip, "-", recordname, zone_match, "- Creating now")
            ipa.dnsrecord_add(zone_match, recordname, {"ptrrecord": [rec_name]})
