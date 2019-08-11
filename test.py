import ipahttp
import pynetbox
import re
import subprocess

ipa = ipahttp.ipa('ipa.tre.esav.fi', sslverify=True)
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

        ptr_records.append((zone, name, ip,))

# print(a_records)
# print(ptr_records)


def get_host(fqdn, zone):
    without_zone = fqdn[:fqdn.index(zone)]
    assert without_zone[-1] == '.'
    return without_zone[:-1]


for zone in zones:
    records = ipa.dnsrecord_find(zone)['result']['result']

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
