from flask_restx.fields import Raw as FlaskRestPlusRawField, Nested as FlaskRestPlusNestedField,\
    List as FlaskRestPlusListField, MarshallingError
from marshmallow import fields
from marshmallow.exceptions import ValidationError

def ModelFromSchema(schema, nestedFieldsMapping = None):
    """
        Creates a marshmallow schema equivalent flask_restx model object

    :param schema: input marshmallow schem from which the flask_restx model is created
    :param nestedFieldsMapping: dictionary for nested fields, where the keys are the marshmallow nested fields and
        the values are the user defined flask_restx model objects
    :return: the marshmallow schema equivalent flask_restx model object
    """

    class FlaskRestPlusField(FlaskRestPlusRawField):
        # __schema_type__ = 'string'

        def __init__(self, mmField: fields.Field):
            super().__init__(attribute=mmField.attribute,
                             required=mmField.required, readonly=mmField.load_only, **mmField.metadata)
            self.m_mmField = mmField
            self.__schema_type__ = self.SchemaTypeByMMField(mmField)

        def format(self, value):
            try:
                # noinspection PyProtectedMember
                self.m_mmField._validate(value) #should throw in case of error
            except ValidationError as e:
                raise MarshallingError(e)
            return value

        @staticmethod
        def SchemaTypeByMMField(mmField):
            for schemaMMFieldMapping in [
                {
                    "mmFieldType": fields.Integer,
                    "schemaType": 'integer'
                },
                {
                    "mmFieldType": fields.Decimal,
                    "schemaType": 'number'
                },
                {
                    "mmFieldType": fields.Float,
                    "schemaType": 'number'
                },
                {
                    "mmFieldType": fields.Boolean,
                    "schemaType": 'boolean'
                },
                {
                    "mmFieldType": fields.Mapping,
                    "schemaType": 'object'
                },
                {
                    "mmFieldType": fields.Dict,
                    "schemaType": 'object'
                },
                {
                    "mmFieldType": fields.Nested,
                    "schemaType": "object"
                },
                {
                    "mmFieldType": fields.List,
                    "schemaType": "array"
                },
            ]:
                if isinstance(mmField, schemaMMFieldMapping["mmFieldType"]):
                    return schemaMMFieldMapping["schemaType"]

            # return SchemaTypeByMMField(mmField.inner) if isinstance(mmField, fields.List) else 'string'
            return 'string'

    res={}
    # noinspection PyProtectedMember
    for fieldName, field in schema._declared_fields.items():
        if not isinstance(field, fields.Nested):
            res[fieldName] = FlaskRestPlusField(field)
        else:
            res[fieldName] = FlaskRestPlusListField(
                FlaskRestPlusNestedField(nestedFieldsMapping[fieldName]["model"],
                                         **nestedFieldsMapping[fieldName]["params"])) if field.many else\
                FlaskRestPlusNestedField(nestedFieldsMapping[fieldName]["model"],
                                         **nestedFieldsMapping[fieldName]["params"]) #nested field result in a recursive call
    return res

# def RowToDict(row):
#     return { col.name: getattr(row, col.name) for col in row.__table__.columns }

def ValidRelationshipIds(relationshipIds, relationshipModel):
    relationshipModelIds = set()
    for row in relationshipModel.query.with_entities(relationshipModel.id).\
            filter(relationshipModel.id.in_(relationshipIds)):
        relationshipModelIds.add(row.id)

    # check if the orgs ids are valid
    for relationshipId in relationshipIds:
        if not relationshipId in relationshipModelIds:
            return False, {
                "invalidId": relationshipId,
            }
    return True, {}
