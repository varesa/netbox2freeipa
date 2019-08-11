import ipahttp
import json
import pynetbox
import random
import string
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


# print((get_zones(ipa)))
# print(json.dumps(list(get_addresses(nb))))

rand = ''.join(random.choice(string.ascii_lowercase) for i in range(5))

r = ipa.dnsrecord_add('my.zone', f"automation-test-{rand}", {"arecord": ["2.3.4.5"]})
print(json.dumps(r))

print(json.dumps(ipa.dnsrecord_find('my.zone')))
