import ipahttp
import json
import subprocess

ipa = ipahttp.ipa('ipa.tre.esav.fi', sslverify=True)
ipa.login(
    'autom_netbox2ipa',
    subprocess.check_output(['secret-tool', 'lookup', 'account', 'autom_netbox2ipa']).decode()
)


def get_zones(ipa):
    reply = ipa.dnszone_find()
    return [zone['idnsname'][0] for zone in reply['result']['result']]


print((get_zones(ipa)))

