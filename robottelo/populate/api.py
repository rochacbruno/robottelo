"""Implements API populator"""
from robottelo.populate.base import BasePopulator
from nailgun import entities
from nailgun.entity_mixins import EntitySearchMixin
from requests.exceptions import HTTPError


class APIPopulator(BasePopulator):
    """Populates system using API/Nailgun"""

    def populate(self, entity_data, raw_entity, search_data):
        """Populates the System using Nailgun
        threats and logs Exceptions
        takes care of adding valid entity to the registry
        """
        model = getattr(entities, raw_entity['model'])

        if not issubclass(model, EntitySearchMixin):
            raise TypeError("{0} not searchable".format(model))

        try:
            # 1) check if entity already exists
            search_result = model().search(**search_data)
            if search_result:
                if len(search_result) > 1:
                    self.logger.info(search_result)
                    raise RuntimeError(
                        "More than 1 item returned "
                        "validate_fields query is not unique"
                    )
                # existent entity should be unique, so it is the first
                # item in search_result
                result = search_result[0]
                self.total_existing += 1
            else:
                result = model(**entity_data).create()
                self.total_created += 1
        except HTTPError as e:
            self.logger.error(str(e))
            if hasattr(e, 'response'):
                self.logger.info(e.response.content)
        else:
            self.add_to_registry(raw_entity, result)

    def validate(self, entity_data, raw_entity, search_data):
        """Based on predefined `search_data` or using
        raw_entity['validate_fields'] searches the system
        and validates the existence of all entities"""
        model = getattr(entities, raw_entity['model'])

        if not issubclass(model, EntitySearchMixin):
            raise TypeError("{0} not searchable".format(model))

        try:
            # 1) check if entity exists
            search_result = model().search(**search_data)
            if search_result:
                if len(search_result) > 1:
                    self.logger.info(search_result)
                    raise RuntimeError(
                        "More than 1 item returned "
                        "validate_fields query is not unique"
                    )
                # existent entity should be unique, so it is the first
                # item in search_result
                result = search_result[0]
                self.total_existing += 1
            else:
                result = None
        except HTTPError as e:
            error_message = str(e)
            if hasattr(e, 'response'):
                error_message += e.response.content
            self.logger.error(error_message)
            self.validation_errors.append({
                'search_data': search_data,
                'message': error_message,
                'entity_data':  entity_data,
                'raw_entity': raw_entity
            })
        else:
            if result:
                self.add_to_registry(raw_entity, result)
            else:
                self.add_to_registry(raw_entity, None)
                self.validation_errors.append({
                    'search_data': search_data,
                    'message': 'entity does not exist in the system',
                    'entity_data':  entity_data,
                    'raw_entity': raw_entity
                })
