"""Boefje script for getting dns records"""
import json
import logging
from typing import Union, Tuple

import dns.resolver
from dns.name import Name
from dns.resolver import Answer

from boefjes.job_models import BoefjeMeta

logger = logging.getLogger(__name__)


class ZoneNotFoundException(Exception):
    pass


def run(boefje_meta: BoefjeMeta) -> Tuple[BoefjeMeta, Union[bytes, str]]:

    hostname = boefje_meta.arguments["input"]["name"]

    requested_dns_name = dns.name.from_text(hostname)
    zone_soa_record = get_parent_zone_soa(requested_dns_name)

    answers = [
        zone_soa_record,
    ]

    dns_record_types = ["A", "AAAA", "TXT", "MX", "NS", "CNAME", "DNAME"]
    for type_ in dns_record_types:

        try:
            answer: Answer = dns.resolver.resolve(hostname, type_)
            answers.append(answer)
        except dns.resolver.NoAnswer:
            pass
        except dns.resolver.NXDOMAIN:
            return boefje_meta, "NXDOMAIN"
        except dns.resolver.Timeout:
            pass

    answers_formatted = [
        f"RESOLVER: {answer.nameserver}\n{answer.response}" for answer in answers
    ]

    results = {
        "dns_records": "\n\n".join(answers_formatted),
        "dmarc_response": get_email_security_records(hostname, "_dmarc"),
        "dkim_response": get_email_security_records(hostname, "_domainkey"),
    }
    return boefje_meta, json.dumps(results)


def get_parent_zone_soa(name: Name) -> Answer:
    while True:

        try:
            return dns.resolver.resolve(name, dns.rdatatype.SOA)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            pass

        try:
            name = name.parent()
        except dns.name.NoParent:
            raise ZoneNotFoundException


def get_email_security_records(hostname: str, record_subdomain: str) -> Union[str, bool]:
    try:
        answer = dns.resolver.resolve(f"{record_subdomain}.{hostname}", "TXT")
        return answer.response.to_text()
    except dns.resolver.NXDOMAIN:
        return "NXDOMAIN"
    except dns.resolver.NoAnswer:
        return "NoAnswer"
    except dns.resolver.Timeout:
        return "Timeout"
