from Database import db #sqlalchemy orm
from sqlalchemy import UniqueConstraint, CheckConstraint

#model used to create the Org db table
class EntityLikeDbModelBase:
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, unique=True, nullable=False)
    country = db.Column(db.String, CheckConstraint("length(country) >= 2"))
    state = db.Column(db.String)
    location = db.Column(db.String)
    email = db.Column(db.String)
    __kind__ = "entity"
    __kinds__ = "entities"

    def PrettyRepr(self):
        return f'{self.__kind__.capitalize()} "{self.name}"'


# class EntityDbModel(object):
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#

class OrgDbModel(db.Model, EntityLikeDbModelBase):
    __tablename__ = "orgs"
    __kind__ = "organization"
    __kinds__ = "organizations"

    # entities = db.relationship("EntityDbModel", secondary="entityOrgBindings", remote_side=[EntityDbModel.id], lazy="dynamic", passive_deletes=True,
    entities = db.relationship("EntityDbModel", secondary="entityOrgBindings", lazy="dynamic", passive_deletes=True,
                               backref=db.backref("orgs", lazy="dynamic", passive_deletes=True)) #the records are deleted by db

    # def GetEntitiesIds(self):
    #     return self.entities.with_entities(EntityDbModel.id).all()

    def __repr__(self):
        return f"Id: {self.id}, Name: {self.name}, Country: {self.country}, State: {self.state}, Location: {self.location}, Email: {self.email}"

from enum import IntEnum

class EntityTypeEnum(IntEnum):
    server = 1 #server entity type
    user = 2 #server entity type

class EntityTypeDbModel(db.Model):
    __tablename__ = "entitiesTypes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Enum(EntityTypeEnum, length=16), unique=True, nullable=False)

#model used to create the Entity db table, for storing users and servers
class EntityDbModel(db.Model, EntityLikeDbModelBase):
    __tablename__ = "entities"

    # type = db.Column(db.Enum(EntityTypeEnum)) #entity type. Enum names will be used and checked
    typeId = db.Column(db.Integer, db.ForeignKey("entitiesTypes.id", ondelete="CASCADE", onupdate="CASCADE"),
                       index=True) #entity type. Enum names will be used and checked
    srvExtraInfo = db.relation("ServersExtraInfoDbModel", uselist=False, passive_deletes=True)

    # def GetOrgsIds(self):
    #     # from sqlalchemy import select
    #     # return db.session.execute()
    #     return [ rec.orgId for rec in EntityOrgBindings.query.with_entities(EntityOrgBindings.orgId).\
    #         filter(EntityOrgBindings.entityId == self.id).all() ]
    #     # return self.orgs.with_entities(g_entityOrgBindingDbTable.entityId).all()
    #     # return self.orgs.with_entities(OrgDbModel.id).all()
    #
    # def SetOrgsIds(self, orgsIds):
    #     if isinstance(self.id, int):
    #         from Api import g_theApi
    #         # dbSession = g_theApi.app.Db().session
    #         dbSession = g_theApi.app.Db().create_scoped_session() #if reusing the app's db session it gives a threading related error
    #         for orgId in orgsIds:
    #             dbSession.add(EntityOrgBindings(entityId = self.id, orgId = orgId))
    #         dbSession.commit()
    #     print("Done")

    # orgsIds = property(GetOrgsIds, SetOrgsIds)
    # orgsIds = property(GetOrgsIds, SetOrgsIds)

    def __repr__(self):
        return f"Id: {self.id}, Name: {self.name}, Country: {self.country}, State: {self.state}, Location: {self.location}, Email: {self.email}"

#to easily allow an entity to be bound to multiple organizations a entity-to-org binding table is used
# g_entityOrgBindingDbTable = db.Table("entityOrgBindings",
#     db.Column("entityId", db.Integer, db.ForeignKey("entities.id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True),
#     db.Column("orgId", db.Integer, db.ForeignKey("orgs.id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True),
#     UniqueConstraint("entityId", "orgId")) #the <entityId>-<orgId> pair must be unique
class EntityOrgBindings(db.Model):
    __tablename__ = "entityOrgBindings"

    entityId = db.Column(db.Integer, db.ForeignKey("entities.id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True)
    orgId = db.Column(db.Integer, db.ForeignKey("orgs.id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True)

    __table_args__ = (UniqueConstraint("entityId", "orgId"),)  # the <entityId>-<orgId> pair must be unique

#model for PKI CA table
class CasDbModel(db.Model):
    __tablename__ = "cas"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    orgId = db.Column(db.Integer, db.ForeignKey('orgs.id', ondelete="CASCADE", onupdate="CASCADE"), unique=True,
                      nullable=False) #the org id is stored, for knowing for which org this CA was generated
    cert = db.Column(db.String, nullable=False) #PEM format
    key = db.Column(db.String, nullable=False) #PEM format
    # certs = db.relationship("CertsDbModel", lazy="dynamic", backref="ca", passive_deletes=True) #Todo: enable it if needed

    def __repr__(self):
        return f"Id: {self.id}, OrgId: {self.orgId}"

#PKI Certs table for both users and servers
class CertsDbModel(db.Model):
    __tablename__ = "certs" # users and servers certificates
    id = db.Column(db.Integer, primary_key=True, autoincrement=True) # it's also the certificate's serial number
    entityId = db.Column(db.Integer, nullable=False)
    orgId = db.Column(db.Integer, db.ForeignKey('cas.orgId', ondelete="CASCADE", onupdate="CASCADE"), nullable=False) #useful for easy regenerating the certificate
    srvType = db.Column(db.Boolean) #true if the certificate identifies a server rather than an user
    revoked = db.Column(db.Boolean, default=False) # true if the certificate is revoked and false otherwise
    cert = db.Column(db.String, nullable=False)
    key = db.Column(db.String, nullable=False)

    def __repr__(self):
        return f"Id: {self.id}, EntityId: {self.entityId}, orgId: {self.orgId}, Server type:{self.srvType}, " \
               f"Revoked:{self.revoked}"

#extra info for servers. For now just openvpn tls crypto key. It's stored independently due to its longer variability
# than servers' certificates'
class ServersExtraInfoDbModel(db.Model):
    __tablename__ = "serversExtraInfo"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    srvId = db.Column(db.Integer, db.ForeignKey('entities.id', ondelete="CASCADE", onupdate="CASCADE"), nullable=False,
                      unique=True) #must be an entity id, with type server
    tlsKey = db.Column(db.String, nullable=False) # openvpn's tls crypt key. See openvpn's "--tls-crypt file" option

    def __repr__(self):
        return f"Id: {self.id}, ServerId: {self.srvId}"
