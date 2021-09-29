from sqlalchemy.orm.exc import NoResultFound
from flask_restx import abort
from Database.Models import EntityDbModel, CasDbModel, CertsDbModel, EntityTypeEnum
from Utils.ResourcesUtils import GetSingle, GetOrg
import os

from Utils.SettingsUtils import EnvOrSetting


def GetOvpnSrv(srvId):
    srv = GetSingle(EntityDbModel, srvId)
    if srv.typeId != EntityTypeEnum.server:
        abort(400, f"Entity id {srvId} doesn't have \"server\" type")
    return srv


def GeOvpnUser(userId):
    user = GetSingle(EntityDbModel, userId)
    if user.typeId != EntityTypeEnum.user:
        abort(400, f"Entity id {userId} doesn't have \"user\" type")
    return user


from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import NameOID
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
import datetime


def GenerateCaByOrgId(app, orgId, configArg=None):
    return GenerateCaByOrg(app, GetOrg(orgId), configArg)

def GenerateCaByOrg(app, org, configArg=None):
    config = {
        "CA": {
            "commonName":
                org.name + " CA",
            "country": CountryCode(org.country),
            "state": org.state,
            "location": org.location,
            "orgName": org.name,
            "email": org.email
        },
        **(configArg if type(configArg) is dict else {})
    }
    return GenerateCa(app, config)

def GenerateCa(app, configArg=None):
    config = {
        "serializedKeys": True,
        "caValidFrom": datetime.datetime.now() - datetime.timedelta(days=1),
        "caValidity": 30 * 365,  # if not specified the validity will be 30 years
        **(configArg if type(configArg) is dict else {}),
        "CA": {
            "commonName": EnvOrSetting("HOST", "FLASK_HOST", "localhost") + " CA",
            "orgUnitName": "CAs",
            **(configArg["CA"] if "CA" in configArg else {})
        },
    }

    caKey: rsa.RSAPrivateKeyWithSerialization = rsa.generate_private_key(65537, 4096, default_backend())

    subject = issuer = x509.Name([
        x509.NameAttribute(entry["nameOID"], config["CA"][entry["name"]]) for entry in (caConfigEntry for caConfigEntry in [{
            "name": "commonName",
            "nameOID": NameOID.COMMON_NAME
        }, {
            "name": "country",
            "nameOID": NameOID.COUNTRY_NAME
        }, {
            "name": "state",
            "nameOID": NameOID.STATE_OR_PROVINCE_NAME
        }, {
            "name": "location",
            "nameOID": NameOID.LOCALITY_NAME
        }, {
            "name": "orgName",
            "nameOID": NameOID.ORGANIZATION_NAME
        }, {
            "name": "email",
            "nameOID": NameOID.EMAIL_ADDRESS
        }, {
            "name": "orgUnitName",
            "nameOID": NameOID.ORGANIZATIONAL_UNIT_NAME
        }
        ] if caConfigEntry["name"] in config["CA"])
    ])
    subjectKeyIdentifier = x509.SubjectKeyIdentifier.from_public_key(caKey.public_key())
    serialNumber = x509.random_serial_number()
    validUntil = config["caValidFrom"] + datetime.timedelta(days=config["caValidity"])
    caCert = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(caKey.public_key()). \
        serial_number(serialNumber). \
        not_valid_before(config["caValidFrom"]). \
        not_valid_after(validUntil). \
        add_extension(subjectKeyIdentifier, critical=False). \
        add_extension(x509.AuthorityKeyIdentifier(subjectKeyIdentifier.digest, [x509.DirectoryName(issuer)],
                                                  serialNumber), critical=False). \
        add_extension(x509.BasicConstraints(True, 0  # CA true and for now we'll not use intermediate CAs
                                            ), critical=False). \
        sign(caKey, hashes.SHA512(), default_backend())  # Sign our certificate with our private key
    return (caCert.public_bytes(encoding=serialization.Encoding.PEM),
            caKey.private_bytes(encoding=serialization.Encoding.PEM,
                                format=serialization.PrivateFormat.PKCS8,
                                encryption_algorithm=serialization.BestAvailableEncryption(b'ToBeSetPasswd'))) if \
        config["serializedKeys"] else (caCert, caKey)


from typing import Tuple, Union


def GetCaCertAndKey(app, orgId, configArg=None) -> Tuple[
    Union[x509.Certificate, bytes], Union[rsa.RSAPrivateKey, bytes]]:
    config = {
        "serializedKeys": True,
        **(configArg if type(configArg) is dict else {})
    }

    def GetCaCertAndKeySerialized() -> tuple:
        try:
            caObj = CasDbModel.query.filter(CasDbModel.orgId == orgId).one()
            return caObj.cert, caObj.key  # the certs and keys are stored in PEM format (serialized)
        except NoResultFound:
            innerSerializedCaCert, innerSerializedCaKey = GenerateCaByOrgId(app, orgId, configArg)
            # add the CA to db
            db = app.Db()
            db.session.add(CasDbModel(
                orgId=orgId,
                cert=innerSerializedCaCert,
                key=innerSerializedCaKey
            ))
            db.session.commit()
            return innerSerializedCaCert, innerSerializedCaKey

    serializedCaCert, serializedCaKey = GetCaCertAndKeySerialized()
    if config["serializedKeys"]:
        return serializedCaCert, serializedCaKey
    else:
        caKey = serialization.load_pem_private_key(serializedCaKey, b'ToBeSetPasswd', default_backend())  # the CA key
        caCert = x509.load_pem_x509_certificate(serializedCaCert, default_backend())
        return caCert, caKey


def GetLastCertificateId():
    lastCertDbObj = CertsDbModel.query.order_by(CertsDbModel.id.desc()).first()
    return 0 if lastCertDbObj is None else lastCertDbObj.id

def CountryCode(countryName):
    from iso3166 import countries

    return countryName if len(countryName) == 2\
    else countries.get(countryName).alpha2 if countryName in countries else countryName[:2].upper()

def GenerateCertAndKeyByEntitiyAndOrgIds(app, entityId, orgId, configArg=None):
    config = {
        "srvType": False,
        **(configArg if type(configArg) == dict else {})
    }
    srvType = config["srvType"]

    entity = GetOvpnSrv(entityId) if srvType else GeOvpnUser(entityId)
    org = GetOrg(orgId)
    caCert, caKey = GetCaCertAndKey(app, orgId, {
        **configArg,
        "serializedKeys": False
    })
    return GenerateCertAndKeyByEntityAndOrg(app, entity, org, caCert, caKey, config)

def GenerateCertAndKeyByEntityAndOrg(app, entity, org, caCert, caKey, configArg=None):
    config = {
        "srvType": False,
        "serialNo": GetLastCertificateId() + 1,
        "entity": {
            "name": entity.name,
            "country": CountryCode(entity.country),
            "state": entity.state,
            "location": entity.location,
            "email": entity.email
        },
        "org": {
            "name": org.name,
            "unitName": "LinyOvpnServers" if type(configArg) == dict and "srvType" in configArg and configArg["srvType"]\
                else "LinyOvpnClients"
        },
        **(configArg if type(configArg) == dict else {})
    }
    return GenerateCertAndKey(app, caCert, caKey, config)

def GenerateCertAndKey(app, caCert, caKey, configArg=None):
    config = {
        "srvType": False,
        "serializedKeys": True,
        # minus one day, for having valid certs regardless server's timezone
        "validFrom": datetime.datetime.now() - datetime.timedelta(days=1),
        "validity": 3 * 365,  # by default the certificates will have approx. three years validity
        "serialNo": 1,
        **(configArg if type(configArg) == dict else {}),
        "entity": {
            "name": EnvOrSetting("HOST", "FLASK_HOST", "localhost"),
            **(configArg["entity"] if type(configArg) == dict and "entity" in configArg else {})
        },
        "org": {
            "name": EnvOrSetting("HOST", "FLASK_HOST", "localhost"),
            "unitName": "Servers" if type(configArg) == dict and "srvType" in configArg and configArg["srvType"] else\
                "Clients",
            **(configArg["org"] if type(configArg) == dict and "org" in configArg else {})
        },
    }
    key = rsa.generate_private_key(65537, 4096,
                                   default_backend())  # the server's key. Can retrieve the public key out of it
    serialNumber = config["serialNo"]
    pubKey = key.public_key()
    subjectKeyIdentifier = x509.SubjectKeyIdentifier.from_public_key(pubKey)
    subjectAttrs = [ x509.NameAttribute(entry["nameOID"], config["entity"][entry["name"]]) for entry in [{
        "name": "country",
        "nameOID": NameOID.COUNTRY_NAME
    }, {
        "name": "state",
        "nameOID": NameOID.STATE_OR_PROVINCE_NAME
    }, {
        "name": "location",
        "nameOID": NameOID.LOCALITY_NAME
    }, {
        "name": "name",
        "nameOID": NameOID.COMMON_NAME
    }] if entry["name"] in config["entity"]
    ] + [ x509.NameAttribute(entry["nameOID"], config["org"][entry["name"]]) for entry in [{
        "name": "name",
        "nameOID": NameOID.ORGANIZATION_NAME
    }, {
        "name": "unitName",
        "nameOID": NameOID.ORGANIZATIONAL_UNIT_NAME
    }] if entry["name"] in config["org"]
    ]
    srvType = config["srvType"]
    if not srvType and "email" in config["entity"]:
        subjectAttrs.append(x509.NameAttribute(NameOID.EMAIL_ADDRESS,
                                               config["entity"]["email"]))  # user certificate also have email address in its subject

    certBuilder = x509.CertificateBuilder(). \
        subject_name(x509.Name(subjectAttrs)). \
        issuer_name(caCert.subject). \
        public_key(pubKey). \
        serial_number(serialNumber). \
        not_valid_before(config["validFrom"]). \
        not_valid_after(config["validFrom"] + datetime.timedelta(days=config["validity"])). \
        add_extension(x509.BasicConstraints(False, None), critical=True). \
        add_extension(subjectKeyIdentifier, critical=False). \
        add_extension(x509.AuthorityKeyIdentifier(caCert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).
                                                  value.digest, [x509.DirectoryName(caCert.subject)],
                                                  caCert.serial_number), critical=False)
    if srvType:  # server certificate
        certBuilder = certBuilder.add_extension(x509.ExtendedKeyUsage([x509.OID_SERVER_AUTH]), critical=False)
    certBuilder = certBuilder.add_extension(
        x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=True,
                      data_encipherment=False, key_agreement=False, key_cert_sign=False,
                      crl_sign=False, encipher_only=False, decipher_only=False), critical=True). \
        add_extension(x509.SubjectAlternativeName([x509.DNSName(config["entity"]["name"])]), critical=False)
    cert = certBuilder.sign(caKey, hashes.SHA512(), default_backend())  # Sign our certificate with CA's private key
    return (cert.public_bytes(serialization.Encoding.PEM),
            key.private_bytes(encoding=serialization.Encoding.PEM,
                              format=serialization.PrivateFormat.PKCS8,
                              encryption_algorithm=serialization.NoEncryption())) if config["serializedKeys"] \
        else (cert, key)


def GetCertAndKey(app, entityId, orgId, configArg=None):
    config = {
        "srvType": False,
        **(configArg if type(configArg) == dict else {})
    }

    def GenerateAndCommitCertKey():
        serializedCaCert, serializedCaKey = GenerateCertAndKeyByEntitiyAndOrgIds(app, entityId, orgId, configArg)
        dbSession = app.Db().session
        dbSession.add(CertsDbModel(
            entityId=entityId,
            orgId=orgId,
            srvType=config["srvType"],
            cert=serializedCaCert,
            key=serializedCaKey))
        dbSession.commit()
        return serializedCaCert, serializedCaKey

    certObj = CertDbObj(entityId, orgId, srvType=config["srvType"])
    if certObj is not None:
        if StateFromCertDbObj(certObj, config) != CertState.VALID:
            return GenerateAndCommitCertKey()
        else:  # the certificate is valid. Just return it from the db
            return certObj.cert, certObj.key  # the certs and keys are stored in PEM format (serialized)
    else:
        return GenerateAndCommitCertKey()


def GenerateTlsKey(app):
    # generate the openvpn's tls key
    import subprocess

    from Utils.SettingsUtils import EnvOrSetting
    ovpnPath = EnvOrSetting("OVPN_PATH", defaultValue="openvpn")
    from sys import platform
    isWindows = platform.startswith('win32')
    isLinux = platform.startswith('linux')
    assert isWindows or isLinux #tested only on windows and linux, for now
    if isWindows:
        from tempfile import mkstemp

        handle, tmpTcKeyPath = mkstemp(prefix="tc-", dir=app.m_tmpDir.name)
        os.close(handle)
        res = subprocess.run([f"{ovpnPath}", "--genkey", "--secret", f"{tmpTcKeyPath}"])
        if res.returncode == 0:
            with open(tmpTcKeyPath, "rb") as tmpTcKey:
                tlsKey = tmpTcKey.read()
            os.remove(tmpTcKeyPath)
            return tlsKey
        else:
            os.unlink(tmpTcKeyPath)
            return None
        # return tmpFile.readlines() if res.returncode == 0 else None
    else:
        res = subprocess.run(f"{ovpnPath} --genkey --secret /dev/stdout", shell=True, stdout=subprocess.PIPE)
        return res.stdout if res.returncode == 0 else None


def GetSrvExtraInfo(app, srvId):
    from Database.Models import ServersExtraInfoDbModel

    dbSession = app.Db().session
    try:
        query = ServersExtraInfoDbModel.query.filter(ServersExtraInfoDbModel.srvId == srvId)
        srvExtraInfoObj: ServersExtraInfoDbModel = query.one()
        if len(srvExtraInfoObj.tlsKey) == 0:
            tlsKey = GenerateTlsKey(app)
            if tlsKey is None:
                abort(500, "Error generating OpenVPN tc key")
            query.update({
                "tlsKey": tlsKey
            })
            dbSession.commit()
            return srvExtraInfoObj.tlsKey
        return srvExtraInfoObj.tlsKey
    except NoResultFound:
        tlsKey = GenerateTlsKey(app)
        if tlsKey is None:
            abort(500, "Error generating OpenVPN tc key")
        # add the keys to db
        dbSession.add(ServersExtraInfoDbModel(
            srvId=srvId,
            tlsKey=tlsKey,
        ))
        dbSession.commit()
        return tlsKey


from enum import Enum, unique


@unique
class CertState(Enum):
    VALID = 0  # the cert is valid
    INVALID = 1  # the system date precedes the cert generation date or the certificate format is invalid
    EXPIRED = 2  # the system date is beyond the cert expiration date
    REVOKED = 3  # the cert is revoked
    NA = 4 #not yet generated (not available)

def QueryCertState(entityId, srvType=True):
    certDbObj = CertDbObj(entityId, srvType=srvType)
    return StateFromCertDbObj(certDbObj) if certDbObj is not None else \
        abort(500, f"Error trying to the the cert state for entity id {entityId} and srv type {srvType}")


def CertFromCertObj(certObj: CertsDbModel) -> x509.Certificate:
    return CertFromSerializedCert(certObj.cert)


def CertFromSerializedCert(serializedCert) -> x509.Certificate:
    return x509.load_pem_x509_certificate(serializedCert, default_backend())


def StateFromCertDbObj(certObj: CertsDbModel, configArg = None):
    if len(certObj.cert) == 0:
        return CertState.NA
    config = {
        **(configArg if type(configArg) is dict else {})
    }
    if "date" not in config or not isinstance(config["date"], datetime.datetime):
        config["date"] = datetime.datetime.now()

    try:
        cert: x509.Certificate = CertFromCertObj(certObj)
        now = config["date"]
        return CertState.INVALID if now < cert.not_valid_before else \
            CertState.EXPIRED if now > cert.not_valid_after else \
                CertState.REVOKED if certObj.revoked else \
                    CertState.VALID
    except:
        return CertState.INVALID

def GetCRL(app, orgId, configArg=None):
    config = {
        "serialize": False,
        **(configArg if type(configArg) == dict else {})
    }
    caCert, caKey = GetCaCertAndKey(app, orgId, {
        "serializedKeys": False
    }) if "caCert" not in config or "caKey" not in config else (config["caCert"], config["caKey"])
    validFrom = datetime.datetime.now() - datetime.timedelta(days=1) if "validFrom" not in config else config["validFrom"]
    crlBuilder = x509.CertificateRevocationListBuilder().issuer_name(caCert.issuer).last_update(validFrom).next_update(
        validFrom + datetime.timedelta(days = 3650 if "validity" not in config else config["validity"])
    )
    # add the revoked certificates
    certsQuery = CertsDbModel.query.filter(CertsDbModel.orgId == orgId)
    for certObj in certsQuery:
        if StateFromCertDbObj(certObj) == CertState.REVOKED:
            # add revoked certificate to crlBuilder
            cert = CertFromCertObj(certObj)
            crlBuilder = crlBuilder.add_revoked_certificate(x509.RevokedCertificateBuilder().serial_number(
                cert.serial_number).revocation_date(validFrom).build(default_backend()))
    crl: x509.CertificateRevocationList = crlBuilder.sign(caKey, hashes.SHA512(), default_backend())
    return crl.public_bytes(serialization.Encoding.PEM) if config["serialize"] else crl


def CertDbObj(entityId, orgId, srvType=False) -> CertsDbModel:
    return CertsDbModel.query.order_by(CertsDbModel.id.desc()). \
        filter(CertsDbModel.entityId == entityId, CertsDbModel.orgId == orgId, CertsDbModel.srvType == srvType).first()


from io import BytesIO


def PackConfigTree(treePath) -> BytesIO:
    import tarfile

    tarFile = BytesIO()
    with tarfile.open(fileobj=tarFile, mode="w:xz") as confTar:
        for root, dirs, files in os.walk(treePath):
            for fileItem in files:
                confTar.add(os.path.join(root, fileItem), fileItem)
            for dirItem in dirs:
                confTar.add(os.path.join(root, dirItem), dirItem)
            break
    tarFile.seek(0)
    return tarFile

def GenerateHostCACertAndKey(app, caCertDir, caCommonName):
    caCert, caKey = GenerateCa(app, {
        "serializedKeys": True,
        "CA": {
            "commonName": caCommonName
        }
    })
    with open(os.path.join(caCertDir, "ca.crt"), mode="wb") as f:
        f.write(caCert)
    with open(os.path.join(caCertDir, "ca.key"), mode="wb", opener=KeysOpener) as f:
        f.write(caKey)

def GenerateHostCertAndKey(app, certsDir, caCertPath, caKeyPath):

    with open(caCertPath, mode="rb") as f:
        caCert = x509.load_pem_x509_certificate(f.read(100000), default_backend())
    with open(caKeyPath, mode="rb") as f:
        caKey = serialization.load_pem_private_key(f.read(100000), b'ToBeSetPasswd', default_backend())
    cert, key = GenerateCertAndKey(app, caCert, caKey, {
        "srvType": True,
        "serializedKeys": True,
        "serialNo": x509.random_serial_number(),
    })
    certsBaseName = f'{app.config["HOST"]}-{app.config["PORT"]}'
    with open(os.path.join(certsDir, certsBaseName + ".crt"), mode="wb") as f:
        f.write(cert)
    with open(os.path.join(certsDir, certsBaseName + ".key"), mode="wb", opener=KeysOpener) as f:
        f.write(key)

def KeysOpener(path, flags):  # used for creating keys files with 0700 rights
    return os.open(path, flags, mode=0o700)

def CertPathFingerprint(certPath):
    with open(certPath, mode="rb") as f:
        return CertFingerprint(x509.load_pem_x509_certificate(f.read(100000), default_backend()))

def CertFingerprint(cert):
    fingerprintAsBytes = cert.fingerprint(hashes.SHA1())
    fingerprintStr = f"{fingerprintAsBytes[0]:02x}".upper()
    for fingerprintByte in fingerprintAsBytes[1:]:
        fingerprintStr += ":" + f"{fingerprintByte:02x}".upper()
    return fingerprintStr
