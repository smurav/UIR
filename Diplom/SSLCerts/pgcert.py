#!/usr/bin/python
__author__ = 'dimv36'
from M2Crypto import RSA, X509, EVP, ASN1
from subprocess import check_output
from datetime import datetime
from optparse import OptionParser
from os import path, getuid
from time import time


DEFAULT_FIELDS = {'C': 'ru',
                  'ST': 'msk',
                  'L': 'msk',
                  'O': 'mephi',
                  'OU': 'kaf36',
                  'CN': check_output("whoami", shell=True)[0].split('\n')[0]}
DEFAULT_PASSWORD = '123456'


def password(*args, **kwargs):
    return DEFAULT_PASSWORD


def check_permissions():
    if getuid() != 0:
        print("Please, login as `root` and try again")
        exit(1)


def make_private_key(bits, output):
    rsa_key = RSA.gen_key(bits, 65537, callback=password)
    if not output:
        output = path.abspath(path.curdir) + "/mykey.pem"
    rsa_key.save_key(output, None)
    return 'Key was saved to %s' % output


def make_request(private_key_file, username, context_string, output):
    private_key = EVP.load_key(private_key_file, callback=password)
    if not private_key:
        raise ValueError, 'Not correct key path'
    request = X509.Request()
    request.set_pubkey(private_key)
    request.set_version(3)
    name = X509.X509_Name()
    name.C = DEFAULT_FIELDS['C']
    name.ST = DEFAULT_FIELDS['ST']
    name.L = DEFAULT_FIELDS['L']
    name.O = DEFAULT_FIELDS['O']
    name.OU = DEFAULT_FIELDS['OU']
    name.CN = username
    if getuid() == 0:
        context = context_string
    else:
        context = check_output("id -Z", shell=True).split('\n')[0]
    if not context:
        raise ValueError, 'Command `id -Z` return with error code'
    name.SC = context
    request.set_subject_name(name)
    request.sign(private_key, 'sha1')
    if not output:
        output = path.abspath(path.curdir) + '/%s.csr' % DEFAULT_FIELDS['CN']
    request.save_pem(output)
    return 'Request was saved to %s' % output


def make_certificate(request_file, ca_private_key_file, ca_certificate_file, output):
    request = X509.load_request(request_file)
    public_key = request.get_pubkey()
    if not request.verify(public_key):
        raise ValueError, 'Error verifying request'
    subject = request.get_subject()
    ca_certificate = X509.load_cert(ca_certificate_file)
    ca_private_key = EVP.load_key(ca_private_key_file, callback=password)
    certificate = X509.X509()
    certificate.set_serial_number(time().as_integer_ratio()[0])
    certificate.set_version(3)
    certificate.set_subject(subject)
    issuer = ca_certificate.get_issuer()
    not_before = ASN1.ASN1_UTCTIME()
    not_before.set_datetime(datetime.today())
    not_after = ASN1.ASN1_UTCTIME()
    not_after.set_datetime(datetime(datetime.today().year + 1, datetime.today().month, datetime.today().day))
    certificate.set_not_before(not_before)
    certificate.set_not_after(not_after)
    certificate.set_issuer(issuer)
    certificate.set_pubkey(public_key)
    certificate.add_ext(X509.new_extension("basicConstraints", "CA:FALSE", 1))
    if not output:
        output = path.abspath(path.curdir) + '/%s.cert' % DEFAULT_FIELDS['CN']
    certificate.sign(ca_private_key, 'sha1')
    certificate.save(output)
    return 'Certificate was saved to %s' % output


def verify_certificate(certificate_file, ca_certificate):
    certificate = X509.load_cert(certificate_file)
    if not certificate:
        raise ValueError, 'Error loading certificate file'
    ca_certificate = X509.load_cert(ca_certificate)
    ca_public_key = ca_certificate.get_pubkey()
    if not ca_certificate:
        raise ValueError, 'Error loading certificate key file'
    if certificate.verify(ca_public_key):
        return 'status verification ok'
    else:
        return 'status: verification failed'


def print_certificate(certificate_file_path):
    if not path.exists(certificate_file_path):
        raise ValueError, 'Certificate path %s not exist' % certificate_file_path
    certificate = X509.load_cert(certificate_file_path)
    return certificate.as_text()


def print_request(request_file_path):
    if not path.exists(request_file_path):
        raise ValueError, 'Request path %s not exist' % request_file_path
    request = X509.load_request(request_file_path)
    return request.as_text()


def make_ca(bits, cakey_file_path, cacert_file_path):
    make_private_key(bits, cakey_file_path)
    private_key = EVP.load_key(cakey_file_path, callback=password)
    if not private_key:
        raise ValueError, 'Error loading CA private key'
    name = X509.X509_Name()
    name.C = DEFAULT_FIELDS['C']
    name.ST = DEFAULT_FIELDS['ST']
    name.L = DEFAULT_FIELDS['L']
    name.O = DEFAULT_FIELDS['O']
    name.OU = DEFAULT_FIELDS['OU']
    name.CN = DEFAULT_FIELDS['O'] + '\'s CA'
    certificate = X509.X509()
    certificate.set_serial_number(1)
    certificate.set_version(1)
    certificate.set_subject(name)
    certificate.set_issuer(name)
    certificate.set_pubkey(private_key)
    not_before = ASN1.ASN1_UTCTIME()
    not_before.set_datetime(datetime.today())
    not_after = ASN1.ASN1_UTCTIME()
    not_after.set_datetime(datetime(datetime.today().year + 2, datetime.today().month, datetime.today().day))
    certificate.set_not_before(not_before)
    certificate.set_not_after(not_after)
    certificate.add_ext(X509.new_extension("basicConstraints", "CA:TRUE", 1))
    certificate.sign(private_key, 'sha1')
    certificate.save(cacert_file_path)
    return 'Certificate was saved to %s' % cacert_file_path


if __name__ == "__main__":
    parser = OptionParser(usage="usage: %prog [--genrsa | --genreq | --gencert | --gencacert | --text] options",
                          add_help_option=True,
                          description="This program use M2Crypto library and can generate X509 certificate "
                                      "with extension field SELinux Context")
    parser.add_option("--genrsa", dest="genrsa", action="store_true", default=False,
                      help="generate private key with bits length")
    parser.add_option("--genreq", dest="genreq", action="store_true", default=False,
                      help="generate request for private key")
    parser.add_option("--gencert", dest="gencert", action="store_true", default=False,
                      help="generate certificate for user")
    parser.add_option("--makeca", dest="makeca", action="store_true", default=False,
                      help="generate ca certificate and private key")
    parser.add_option("--text", dest="print_pem", action="store_true", default=False,
                      help="print request or certificate")
    parser.add_option("--verify", dest="verify", action="store_true", default=False, help="verify certificate")
    parser.add_option("--user", dest="user", default=DEFAULT_FIELDS['CN'], help="add username to certificate CN")
    parser.add_option("--context", dest="context", default=None, help="add user context to certificate")
    parser.add_option("--bits", dest="bits", type="int", default="2048", help="bits for generate RSA-key")
    parser.add_option("--request", dest="request", help="add path to request file")
    parser.add_option("--cakey", dest="cakey", default="/etc/pki/CA/private/cakey.pem", type="string",
                      help="add CA key path to generate user's certificate")
    parser.add_option("--cacert", dest="cacert", default="/etc/pki/CA/cacert.pem", type="string",
                      help="add CA certificate path to generate user's certificate")
    parser.add_option("--pkey", dest="pkey", help="add path of private key")
    parser.add_option("--cert", dest="certificate", help="add path of certificate")
    parser.add_option("--output", type="string", dest="output", help="save to file output")
    options, args = parser.parse_args()
    user = options.user
    context = options.context
    bits = options.bits
    request = options.request
    cakey = options.cakey
    cacert = options.cacert
    pkey = options.pkey
    certificate = options.certificate
    output = options.output
    if options.genrsa and options.bits:
        print(make_private_key(bits, output))
    elif options.genreq and options.pkey:
        print(make_request(pkey, user, context, output))
    elif options.gencert and options.request:
        check_permissions()
        print(make_certificate(request, cakey, cacert, output))
    elif options.verify and options.certificate and options.cacert:
        print(verify_certificate(certificate, cacert))
    elif options.print_pem and options.certificate:
        print(print_certificate(certificate))
    elif options.print_pem and options.request:
        print(print_request(request))
    elif options.makeca:
        check_permissions()
        print(make_ca(bits, cakey, cacert))
    else:
        parser.print_help()